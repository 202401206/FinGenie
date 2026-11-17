# Parsers - Backend team

`bank_statement/` parses supported bank statement CSV and XLSX formats (Sprint 1).  
`balance_sheet/` parses supported balance sheet CSV and XLSX formats (Sprint 2).

See [contracts/balance-sheet-layouts.md](../../../contracts/balance-sheet-layouts.md) for detailed layout schemas, canonical field mappings, and unmapped reason codes.  
See [HANDOFF.md](HANDOFF.md) for endpoint integration, exception mapping, and database persistence guidelines.

---

## Supported Layouts Matrix

### 1. Bank Statements (Sprint 1)
| Attribute | Layout 1 (Standard Retail / Demo) | Layout 2 (Commercial Statement B) |
| :--- | :--- | :--- |
| **Date Column** | `Date`, `Transaction Date`, `Value Date` | `Txn Date`, `Posting Date`, `Trans Date` |
| **Description Column** | `Description`, `Narration`, `Details` | `Particulars`, `Transaction Details`, `Remarks` |
| **Debit Column** | `Debit`, `Withdrawal`, `Dr` | `Withdrawal (Dr)`, `Withdrawals (Dr)`, `Dr Amount`, `Debit Amount` |
| **Credit Column** | `Credit`, `Deposit`, `Cr` | `Deposit (Cr)`, `Deposits (Cr)`, `Cr Amount`, `Credit Amount` |
| **Balance Column** | `Balance`, `Closing Balance`, `Running Balance` | `Net Balance`, `Available Balance`, `Account Balance` |
| **Supported Dates** | ISO `YYYY-MM-DD` | Delimited `DD/MM/YYYY`, `DD-MM-YYYY` |
| **File Types** | CSV (`.csv`) and XLSX (`.xlsx`) | CSV (`.csv`) and XLSX (`.xlsx`) |

### 2. Balance Sheets (Sprint 2)
| Attribute | Layout A (Single-Period) | Layout B (Comparative) |
| :--- | :--- | :--- |
| **Header Columns** | `Particulars,Amount` | `Particulars,[Note No],<YYYY-MM-DD>,<YYYY-MM-DD>` |
| **Note Column** | N/A | Optional (`Note No`, `Note`, `Notes`) |
| **Period Columns** | Single amount column | Two or more dated columns |
| **Period Selection** | Extracted directly | Deterministically selects column matching declared `reporting_date` |
| **Prior Period Handling** | N/A | Preserved separately in `unmapped` with `reason="prior_period_value"` |
| **File Types** | CSV (`.csv`) and XLSX (`.xlsx`) | CSV (`.csv`) and XLSX (`.xlsx`) |

---

## Processing Rules & Security Boundaries

### 1. CSV Format
- **Encoding:** UTF-8 and UTF-8 with BOM (`utf-8-sig`).
- **Logical Rows:** Enumerated 1-based records via standard `csv.reader`, accurately counting quoted multiline fields as single rows.
- **Amounts:** Parsed directly from numeric text to `Decimal` without converting through binary float.
- **Limits:** 5 MiB file size, 20,000 rows, 50 columns.

### 2. XLSX Format
- **Container Security:** Treated as untrusted ZIP archives. Checked for magic bytes (`PK\x03\x04`), max 500 archive entries, 5 MiB upload size, and 25 MiB uncompressed size limit to guard against decompression bombs. Macro-enabled workbooks (`.xlsm` / `vbaProject.bin`) are strictly rejected. XML DTD attacks prevented via `defusedxml`.
- **Worksheet Selection:** Scans candidate sheets; ignores empty or cover sheets. Exactly one sheet must match the supported transaction table headers. Multiple matching sheets raise `AmbiguousWorksheetError`; zero matches raise `UnsupportedFormatError`. The exact sheet name is saved in `source_metadata.sheet_name`.
- **Row Provenance:** Uses exact Excel row numbers (`cell.row`, 1-based) for `source_row` and `source_locations`.
- **Formulas:** Formulas in financial or date cells are strictly rejected (`InvalidStatementError`) to avoid trusting unverified or stale cached values.
- **Numeric Precision:** Integer cells convert to `Decimal(int)`. Float cells convert via `Decimal(str(float))` using shortest base-10 string representation. Formatted text numbers are parsed directly using Decimal.
- **Traceability:** Unrecognized preamble rows, summary lines, or footer metadata are preserved in `unmapped`.
