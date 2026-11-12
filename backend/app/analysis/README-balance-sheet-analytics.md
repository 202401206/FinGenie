# Balance Sheet Analytics Engine

Deterministic calculation module for corporate balance sheet analytics, financial KPIs, liquidity assessment, and 1-based source traceability.

## Ownership & Scope
- **Owner**: Aarushi Shah
- **Component**: Balance Sheet Analytics
- **Module**: `backend/app/analysis/balance_sheet_kpis.py`
- **Tests**: `backend/tests/analysis/test_balance_sheet_kpis.py`
- **Shared Contracts**: [`contracts/README.md`](../../../contracts/README.md), [`contracts/examples/balance-sheet.json`](../../../contracts/examples/balance-sheet.json), and [`contracts/examples/balance-sheet-analysis.json`](../../../contracts/examples/balance-sheet-analysis.json)

---

## Capabilities & Mathematical Specifications

### 1. Working Capital (`balance_sheet.working_capital.v1`)
- **Formula**: `(sum(current_assets) - sum(current_liabilities)) * unit_scale`
- **Base Currency Conversion**: Uses `unit_scale` from the balance sheet (1 = units, 1,000 = thousands, 100,000 = lakhs, 10,000,000 = crores) to scale into base currency (e.g. INR 7,000,000).
- **Exact Decimal Arithmetic**: Implemented strictly with Python `Decimal` to avoid floating-point inaccuracies.
- **Traceability**: Retains 1-based source row indices for `unit_scale` and all contributing current asset and current liability line items (`source_rows: [3, 6, 7, 12]`).

### 2. Current Ratio (`balance_sheet.current_ratio.v1`)
- **Formula**: `sum(current_assets) / sum(current_liabilities)`
- **Reported Units**: Ratios are unitless (`unit: "ratio"`) and do not apply unit scaling.
- **Zero-Division Guard**: If current liabilities equal zero, safely returns `status="unavailable"` with a clear descriptive reason rather than raising an unhandled exception.

### 3. Balance Reconciliation Difference (`balance_sheet.balance_difference.v1`)
- **Formula**: `Total Assets - (Total Liabilities + Total Equity)`
- **Balanced Check**: A difference of `Decimal("0")` indicates a perfectly reconciled balance sheet. Discrepancies trigger `reliability="unreliable"` with informative warnings.
- **Traceability**: Retains 1-based source rows for `unit_scale`, `assets.total`, `liabilities.total`, and `equity.total` (`source_rows: [3, 10, 16, 20]`).

### 4. Full Analysis Envelope (`analyze_balance_sheet`)
- Conforms to [`contracts/examples/balance-sheet-analysis.json`](../../../contracts/examples/balance-sheet-analysis.json).
- Returns `workspace_id`, `document_type: "balance_sheet"`, `currency`, `reliability`, `metrics`, and `warnings`.
- Validates missing currency, missing unit scale, and missing sections defensively.

---

## Verification & Testing

Automated test cases are located in [`backend/tests/analysis/test_balance_sheet_kpis.py`](../../tests/analysis/test_balance_sheet_kpis.py).

To execute tests from `backend/`:
```bash
python -m pytest tests/analysis/test_balance_sheet_kpis.py -v
```

Verified Scenarios:
- `test_working_capital_contract_fixture`: Exact 7,000,000 INR working capital matching contract fixture.
- `test_balance_difference_contract_fixture`: Exact 0 INR reconciliation difference.
- `test_current_ratio_contract_fixture`: Exact 1.875 current ratio with source row traceability.
- `test_current_ratio_zero_division_guard`: Clean unavailable status on zero liabilities.
- `test_analyze_balance_sheet_full_contract_envelope`: Complete contract compliance with `balance-sheet-analysis.json`.
- `test_balance_sheet_various_unit_scales`: Verifies units, thousands, lakhs, and crores multipliers.
- `test_unbalanced_balance_sheet_triggers_unreliable_warning`: Detects accounting discrepancies.
- `test_missing_currency_triggers_unreliable`: Identifies unconfirmed monetary units.
- `test_missing_unit_scale_triggers_insufficient_data`: Safeguards against unscaled amounts.
- `test_defensive_type_checks_dirty_corrupt_data`: Robust handling of dirty and malformed line items.
- `test_serialize_balance_sheet_analysis_result`: JSON serialization verification.
