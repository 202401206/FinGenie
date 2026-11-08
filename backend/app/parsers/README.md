# Parsers - Backend team

`bank_statement/` parses supported bank statement CSV and XLSX formats; `balance_sheet/` is reserved for Sprint 2.

## Supported Formats & Rules

### 1. CSV Format
- **Encoding:** UTF-8 and UTF-8 with BOM (`utf-8-sig`).
- **Logical Rows:** Enumerated 1-based records via standard `csv.reader`, accurately counting quoted multiline fields as single rows.
- **Amounts:** Parsed directly from numeric text to `Decimal` without converting through binary float.
- **Limits:** 5 MiB file size, 10,000 transaction rows, 50 columns.

### 2. XLSX Format
- **Container Security:** Treated as untrusted ZIP archives. Checked for magic bytes (`PK\x03\x04`), max 500 archive entries, 5 MiB upload size, and 25 MiB uncompressed size limit to guard against decompression bombs. Macro-enabled workbooks (`.xlsm` / `vbaProject.bin`) are strictly rejected.
- **Worksheet Selection:** Scans candidate sheets; ignores empty or cover sheets. Exactly one sheet must match the supported transaction table headers. Multiple matching sheets raise `AmbiguousWorksheetError`; zero matches raise `UnsupportedFormatError`. The exact sheet name is saved in `source_metadata.sheet_name`.
- **Row Provenance:** Uses exact Excel row numbers (`cell.row`, 1-based) for `source_row` and `source_locations`.
- **Formulas:** Formulas in financial or date cells are strictly rejected (`InvalidStatementError`) to avoid trusting unverified or stale cached values.
- **Numeric Precision:** Integer cells convert to `Decimal(int)`. Float cells convert via `Decimal(str(float))` using shortest base-10 string representation. Formatted text numbers are parsed directly using Decimal.
- **Traceability:** Unrecognized preamble rows, summary lines, or footer metadata are preserved in `unmapped`.
