# FinGenie — Bank Statement Analytics Engine

**Prepared by:** Aarushi Shah (Student ID: 202401193)  
**Track:** Bank Statement Analytics  
**Component:** `backend/app/analysis/bank_kpis.py`  
**Target Milestone:** Sprint 2 & Sprint 3 Integration  
**Interface Contract:** [`docs/ai-and-analysis-integration-guide.md`](../../../docs/ai-and-analysis-integration-guide.md) & [`contracts/README.md`](../../../contracts/README.md)

---

## 1. Overview & Purpose

The **Bank Statement Analytics Engine** provides deterministic, mathematically exact calculations for all bank statement KPIs and metrics in FinGenie.

It acts as the single source of truth for bank calculations across FinGenie, serving:
1. **AI Assistant & Tool Calling (`backend/app/ai/tools.py`):** Directly supplies calculated values for user queries (e.g., total credit, total debit, net cash flow, closing balance).
2. **Analysis API (`GET /api/workspaces/{id}/analysis`):** Produces the standardized financial analysis contract payload matching [`contracts/examples/financial-analysis.json`](../../../contracts/examples/financial-analysis.json).

This module strictly adheres to the team architecture boundary:
- **Zero float arithmetic:** All financial calculations strictly use Python's `Decimal` to avoid binary floating-point drift.
- **Traceable 1-based source rows:** Captures exact original spreadsheet rows (e.g., Row 6 to Row 8) and JSON field paths (`transactions[i].credit`). Never fabricates row indices.
- **Missing data preservation:** Missing fields (such as missing closing balance or missing currency) return `None` or report status as unavailable with warnings, rather than fabricating zeros.
- **Zero external dependencies:** Pure Python implementation without database, HTTP, LLM, or environment-secret dependencies, allowing deterministic local unit testing.

---

## 2. Implemented Interface Contracts

### Required AI Tool Signatures

```python
from decimal import Decimal
from typing import Any

def calculate_total_credit(data: dict[str, Any]) -> Decimal:
    """Calculates sum of all incoming transactions (credit > 0)."""
    ...

def calculate_total_debit(data: dict[str, Any]) -> Decimal:
    """Calculates sum of all outgoing transactions (debit > 0)."""
    ...

def calculate_net_cash_flow(data: dict[str, Any]) -> Decimal:
    """Calculates total credits minus total debits."""
    ...

def get_closing_balance(data: dict[str, Any]) -> Decimal | None:
    """Retrieves closing balance, or returns None if missing in the statement data."""
    ...
```

### Traceability & Extended Contract Helpers

```python
def get_opening_balance(data: dict[str, Any]) -> Decimal | None:
    """Retrieves opening balance, or returns None if missing."""
    ...

def get_total_credit_source_refs(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extracts 1-based source rows and field paths for credit transactions."""
    ...

def get_total_debit_source_refs(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extracts 1-based source rows and field paths for debit transactions."""
    ...

def get_net_cash_flow_source_refs(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extracts combined 1-based source rows and field paths for net cash flow."""
    ...

def get_closing_balance_source_refs(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extracts 1-based source row and field path for closing balance."""
    ...

def calculate_bank_analysis(
    data: dict[str, Any],
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Generates complete financial analysis response matching contracts/examples/financial-analysis.json."""
    ...
```

---

## 3. How Prince's AI Tools Integrate with This Module

In `backend/app/ai/tools.py`:
```python
from app.analysis.bank_kpis import (
    calculate_total_credit,
    calculate_total_debit,
    calculate_net_cash_flow,
    get_closing_balance,
)

# When user asks: "How much did I spend this month?"
total_debits = calculate_total_debit(workspace_data)

# When user asks: "What is my net cash flow?"
net_flow = calculate_net_cash_flow(workspace_data)

# When user asks: "What is my closing balance?"
closing = get_closing_balance(workspace_data)
```

---

## 4. Test Verification & Results

Automated test cases are located in [`backend/tests/analysis/test_bank_kpis.py`](../../tests/analysis/test_bank_kpis.py).

To execute tests from `backend/`:
```bash
python -m pytest tests/analysis/test_bank_kpis.py -v
```

Verified Test Scenarios:
- `test_calculate_total_credit_fixture`: Correctly computes 5,000 INR from `bank-statement.json`.
- `test_calculate_total_debit_fixture`: Correctly computes 2,500 INR from `bank-statement.json`.
- `test_calculate_net_cash_flow_fixture`: Correctly computes 2,500 INR net cash flow.
- `test_get_closing_balance_fixture`: Correctly extracts 12,500 INR closing balance.
- `test_get_opening_balance_fixture`: Correctly extracts 10,000 INR opening balance.
- `test_decimal_precision_no_float_drift`: Verifies exact decimal precision on fractional cents (`0.10 + 0.20 = 0.30`).
- `test_empty_statement_returns_zeros_and_none`: Safely handles empty dictionary inputs.
- `test_missing_or_none_fields_in_transactions`: Handles non-numeric or missing data cleanly.
- `test_source_rows_traceability_*`: Confirms exact 1-based row numbers (`[6]`, `[7, 8]`, `[6, 7, 8]`, `[9]`).
- `test_calculate_bank_analysis_full_contract_envelope`: Validates complete contract schema compliance with `financial-analysis.json`.
- `test_unreliable_analysis_when_currency_missing`: Confirms unconfirmed currency triggers `unreliable` reliability flag and warnings.
