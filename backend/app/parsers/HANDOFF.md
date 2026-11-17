# FinGenie Parsers — Handoff Guide (Sprint 1 & Sprint 2)

**Target Audience:** Anshuman (API / Routes), Project Lead (Persistence / Database), and AI + Analysis Team  
**Author:** Dhaval Popat (Financial Statement Parsers)  
**Branch:** `feature/backend-sprint-2-parsers` $\rightarrow$ Target PR Base: `feature/backend-sprint-2`

---

## 1. Quick Integration Summary

All parsers are completely pure and synchronous: **no database calls, no Supabase, no HTTP requests, and no LLMs**.

* **Bank Statements:** `parse_bank_statement(content: bytes, *, file_kind: str, document_id: UUID) -> BankStatement`
* **Balance Sheets:** `parse_balance_sheet(content: bytes, *, file_kind: str, document_id: UUID) -> BalanceSheet`

Both return validated Pydantic models whose `model_dump(mode="python")` preserves exact `Decimal`, `datetime.date`, and `UUID` objects.

```python
from app.parsers.balance_sheet import parse_balance_sheet
from app.parsers.bank_statement import parse_bank_statement
from app.parsers.errors import (
    AmbiguousWorksheetError,
    BalanceSheetParserError,
    BankStatementParserError,
    InvalidStatementError,
    ResourceLimitError,
    StatementParserError,
    UnsupportedFormatError,
)
from app.schemas.balance_sheet import BalanceSheet
from app.schemas.bank_statement import BankStatement
```

---

## 2. API Route & Upload Dispatch (For Anshuman)

### Business vs. Personal Upload Rules
* **Business Users:** May upload both `bank_statement` and `balance_sheet` documents.
* **Personal Users:** May upload `bank_statement` only. Reject `balance_sheet` uploads for personal users with `403 Forbidden` or `422 Unprocessable Entity`.

### Worker Boundary
Because parsing handles file decompression and parsing, execute within FastAPI's threadpool:
```python
from starlette.concurrency import run_in_threadpool

statement = await run_in_threadpool(
    parse_balance_sheet,
    file_bytes,
    file_kind=file_ext,
    document_id=document_id,
)
```

### Safe Error Handling Boundary
All parser exceptions inherit from `StatementParserError`. Catch `StatementParserError` in the orchestration boundary so expected user errors return clean 4xx responses rather than escaping as 500:

| Parser Exception | HTTP Status | Trigger / Meaning |
| :--- | :--- | :--- |
| `UnsupportedFormatError` | **415** / **422** | Unsupported file format, corrupted archive, or unrecognized table headers. |
| `ResourceLimitError` | **413** / **422** | File > 5 MiB, expanded XLSX > 25 MiB, > 500 ZIP entries, > 50 columns, or > 20,000 rows. |
| `AmbiguousWorksheetError` | **422** | XLSX contains multiple candidate sheets matching table headers. |
| `InvalidStatementError` | **422** | Missing reporting date, ambiguous period columns, non-numeric amounts, or formula in cells. |

### Safe Failure / No-Write Guarantee
Parsing is strictly read-only and happens **before** storage reservations, database writes, or journal commits. If parsing fails, no database rows or storage blobs are created.

---

## 3. Database Persistence Boundary (For Project Lead)

The parser output directly satisfies `ParsedBalanceSheet` in [`backend/app/db/parsed_read_models.py`](file:///e:/Projects/FinGenie/backend/app/db/parsed_read_models.py):

```python
# Extract exact python types
db_payload = statement.model_dump(mode="python")

# Validates cleanly against internal reader
from app.db.parsed_read_models import ParsedBalanceSheet

read_model = ParsedBalanceSheet.model_validate(db_payload)
```

### Stored Contract Guarantees:
1. **Exact Decimals in Reported Units:** All amounts remain native `Decimal` in reported units. No floats or booleans exist.
2. **Nullable Metadata:** `company`, `currency`, and `unit_scale` may be `None`. Missing amounts are `None` (never fabricated zero).
3. **Source Traceability:** 
   * `source_metadata.document_id`: Caller's document UUID is preserved verbatim.
   * `source_metadata.sheet_name`: `None` for CSV, exact sheet title string for XLSX.
   * `source_locations`: Maps scalar fields (`company`, `reporting_date`, `currency`, `unit_scale`, `assets.total`, `liabilities.total`, `equity.total`) to `{"source_row": int}`.
   * `source_row`: Preserved on every `LineItem` and `UnmappedItem`.
4. **Prior-Period Values:** Stored in `unmapped` with `reason="prior_period_value"` and `raw_value="<Date>: <Amount>"`.

---

## 4. Financial Calculations & Rules (For AI + Analysis Team)

1. **Unit Scaling:**
   * Values are stored in **reported units** (e.g. `100` for 100 Lakhs).
   * Downstream analysis must multiply by `unit_scale` (`1`, `1000`, `100000`, `1000000`, `10000000`) exactly **once**. The parser does not pre-scale amounts.
   * Ratios (e.g. Current Ratio, Debt-to-Equity) are never multiplied by `unit_scale`.
2. **Reported Totals vs Leaf Items:**
   * `assets.total`, `liabilities.total`, and `equity.total` capture the reported totals from the document.
   * Section subtotals (e.g. `Total Current Assets`) are preserved in `unmapped` (`reason="reported_subtotal"`) and are **never** included in `current` or `non_current` leaf item lists, preventing duplicate summing.
3. **Unbalanced Sheets:**
   * If $\text{Assets} \neq \text{Liabilities} + \text{Equity}$, the parser does not alter or balance the numbers. It stores them as reported for analysis to evaluate reliability (`reliability="unreliable"`).
4. **Negative Values:**
   * `equity.retained_earnings` allows negative Decimals representing accumulated losses/deficits.

---

## 5. Supported Layouts & Test Fixtures

| Layout | Description | Test Fixture Paths |
| :--- | :--- | :--- |
| **Layout A (CSV)** | Single-period `Particulars,Amount` with section headers | `backend/tests/parsers/fixtures/synthetic_balance_sheet_layout_a.csv`<br>`backend/tests/parsers/fixtures/synthetic_balance_sheet_layout_a.json` |
| **Layout B (CSV)** | Comparative `Particulars,[Note No],2026-03-31,2025-03-31` | `backend/tests/parsers/fixtures/synthetic_balance_sheet_layout_b.csv`<br>`backend/tests/parsers/fixtures/synthetic_balance_sheet_layout_b.json` |
| **Minimal (JSON)** | Minimal valid model with all optional metadata null | `backend/tests/parsers/fixtures/balance_sheet_minimal.json` |
| **Layout A (XLSX)** | In-memory generated workbook matching Layout A | Verified in `test_balance_sheet_xlsx_parser.py` |
| **Layout B (XLSX)** | In-memory generated workbook matching Layout B | Verified in `test_balance_sheet_xlsx_parser.py` |
