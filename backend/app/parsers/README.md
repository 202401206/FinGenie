# Parsers - Backend team

`bank_statement/` parses supported bank statement CSV and XLSX formats; `balance_sheet/` is reserved for Sprint 2.

## Supported Layouts Matrix

The parser deterministically matches statement tables against reviewed header aliases and date conventions without fuzzy guessing or LLMs:

| Attribute | Layout 1 (Standard Retail / Demo) | Layout 2 (Commercial Statement B) |
| :--- | :--- | :--- |
| **Date Column** | `Date`, `Transaction Date`, `Value Date` | `Txn Date`, `Posting Date`, `Trans Date` |
| **Description Column** | `Description`, `Narration`, `Details` | `Particulars`, `Transaction Details`, `Remarks` |
| **Debit Column** | `Debit`, `Withdrawal`, `Dr` | `Withdrawal (Dr)`, `Withdrawals (Dr)`, `Dr Amount`, `Debit Amount` |
| **Credit Column** | `Credit`, `Deposit`, `Cr` | `Deposit (Cr)`, `Deposits (Cr)`, `Cr Amount`, `Credit Amount` |
| **Balance Column** | `Balance`, `Closing Balance`, `Running Balance` | `Net Balance`, `Available Balance`, `Account Balance` |
| **Supported Dates** | ISO `YYYY-MM-DD` | Delimited `DD/MM/YYYY`, `DD-MM-YYYY` |
| **Extra Columns** | Unrecognized extra columns (e.g. `Chq/Ref No`, `Value Date`) do not break column mapping |
| **Preamble Metadata** | Bank, Account Holder, Type, Currency, Period, Opening Balance | Bank, Account Holder, Type, Currency, Statement Period, Opening Balance |
| **File Types** | CSV (`.csv`) and XLSX (`.xlsx`) | CSV (`.csv`) and XLSX (`.xlsx`) |

---

## Processing Rules & Security Boundaries

### 1. CSV Format
- **Encoding:** UTF-8 and UTF-8 with BOM (`utf-8-sig`).
- **Logical Rows:** Enumerated 1-based records via standard `csv.reader`, accurately counting quoted multiline fields as single rows.
- **Amounts:** Parsed directly from numeric text to `Decimal` without converting through binary float.
- **Limits:** 5 MiB file size, 10,000 transaction rows, 50 columns.

### Row and column validation

CSV and XLSX share the same header matcher. Each required amount/description
field must map to one column; duplicate names or aliases are rejected. A single
transaction/posting date takes precedence over a separate Value Date, regardless
of column order. Value Date is used when it is the only date field. Multiple
transaction date columns are ambiguous and are rejected.

A short financial row rejects the statement instead of silently losing a
transaction. One/two-cell nonfinancial notes remain in `unmapped`, with their
original source rows. Footer matching uses complete summary labels. A narration
containing "Total" or "Closing balance" still represents a transaction when the
mapped date is present. Actual supported closing-balance footers are retained.

### 2. XLSX Format
- **Container Security:** Treated as untrusted ZIP archives. Checked for magic bytes (`PK\x03\x04`), max 500 archive entries, 5 MiB upload size, and 25 MiB uncompressed size limit to guard against decompression bombs. Macro-enabled workbooks (`.xlsm` / `vbaProject.bin`) are strictly rejected.
- **Worksheet Selection:** Scans candidate sheets; ignores empty or cover sheets. Exactly one sheet must match the supported transaction table headers. Multiple matching sheets raise `AmbiguousWorksheetError`; zero matches raise `UnsupportedFormatError`. The exact sheet name is saved in `source_metadata.sheet_name`.
- **Row Provenance:** Uses exact Excel row numbers (`cell.row`, 1-based) for `source_row` and `source_locations`.
- **Formulas:** Formulas in financial or date cells are strictly rejected (`InvalidStatementError`) to avoid trusting unverified or stale cached values.
- **Numeric Precision:** Integer cells convert to `Decimal(int)`. Float cells convert via `Decimal(str(float))` using shortest base-10 string representation. Formatted text numbers are parsed directly using Decimal.
- **Booleans:** TRUE/FALSE are rejected in monetary cells; they never become 1/0.
- **Worksheet Coordinates:** Every sheet, including covers, must stay within row
  20,000 and column 50 (AX), including blank gaps and styled cells. Declared
  dimensions and actual row/cell references are checked before loading workbook
  cells. Missing or understated dimensions cannot hide distant coordinates.
- **Traceability:** Unrecognized preamble rows, summary lines, or footer metadata are preserved in `unmapped`.
