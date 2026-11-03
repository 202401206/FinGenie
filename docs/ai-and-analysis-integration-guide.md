# FinGenie AI + Analysis Team: Integration Guide & Interface Contract

**Document Owner:** Prince Patel (AI 2: Conversational Assistant & AI Integration)  
**Collaborators:** Rashi Patel (Bank Analytics), Aarushi Shah (Balance Sheet Analytics), Srujan (Number Guard)  
**Target Milestone:** Sprint 2 & Sprint 3 Integration  
**Last Updated:** November 2, 2026 (Aligned with Team Option A & Metric Dictionary Standards)  
**Reference Contracts:** [`contracts/README.md`](../contracts/README.md) and [`contracts/api/README.md`](../contracts/api/README.md)

---

## 1. Team Ownership & Architecture Boundary (Option A Alignment)

Per the team consensus on Slack (Option A), our team responsibilities and file ownership are formally mapped as follows:

| Team Member | Component / Track | Target File Path | Primary Responsibility |
| :--- | :--- | :--- | :--- |
| **Rashi Patel** | Bank Statement Analytics | `backend/app/analysis/bank_kpis.py` | Deterministic calculations for deposits, debits, cash flow, closing balance, and balance reconciliation. |
| **Aarushi Shah** | Balance Sheet Analytics | `backend/app/analysis/balance_sheet_kpis.py` | Deterministic calculations for working capital (scaled), current ratio (liquidity), and balance reconciliation. |
| **Srujan** | Numeric Verification Guard | `backend/app/ai/number_guard.py` | Post-generation safety filter validating that all numbers in AI text match verified calculation results. |
| **Prince Patel** | AI Integration & Assistant | `backend/app/ai/` & `backend/app/api/routes/ai.py` | LLM provider adapter, deterministic tool routing, executive summary engine, multi-turn conversational loop, and API endpoints. |

---

## 2. Shared Financial Data Conventions

Per the team contract in [`contracts/README.md`](../contracts/README.md), all calculation and safety code must strictly adhere to:
1. **Exact Precision (`Decimal`):** Never use binary Python `float` for monetary math. Always use `from decimal import Decimal`.
2. **1-Based Source Rows:** `source_row` indices must correspond to the original 1-based spreadsheet row or CSV record (e.g., Row 6 to Row 205). Never fabricate row numbers (e.g., `i + 1`).
3. **Preserve Missing Data:** Never fabricate a `0` or default `"INR"` if a document is missing amounts, closing balance, or currency. Report missing fields cleanly with `status="unavailable"` and a descriptive `reason`.
4. **Resilient Number Parsing:** In `_to_decimal()`, sanitize string inputs by stripping commas and whitespace (`str(val).replace(",", "").strip()`) before converting to `Decimal`, so that real-world bank CSV exports (e.g., `"1,500.00"` or `"1,50,000.00"`) do not fail.
5. **Standardized Metric Dictionary Contract:** All analysis KPI functions return a complete, self-describing metric dictionary matching the envelope in [`contracts/examples/financial-analysis.json`](../contracts/examples/financial-analysis.json):
   ```python
   {
       "key": "total_credit",
       "value": Decimal("5000"),        # Exact Decimal or None
       "unit": "INR",                   # Currency code or "ratio"
       "status": "available",           # "available" or "unavailable"
       "reason": None,                  # None if available, explanation string if unavailable
       "calculation_id": "bank.total_credit.v1",
       "source_refs": [
           {
               "document_id": "10000000-0000-4000-8000-000000000001",
               "sheet_name": None,
               "source_rows": [6],
               "field_paths": ["transactions[0].credit"],
           }
       ],
   }
   ```

---

## 3. Rashi's Integration Guide: `backend/app/analysis/bank_kpis.py`

Prince's AI tool engine (`backend/app/ai/tools.py`) routes conversational bank queries directly to your functions.

### Implemented & Expected Function Signatures:
```python
from typing import Any

def calculate_total_credit(statement_data: dict[str, Any]) -> dict[str, Any]:
    """Calculates sum of all incoming transactions (credit > 0)."""
    ...

def calculate_total_debit(statement_data: dict[str, Any]) -> dict[str, Any]:
    """Calculates sum of all outgoing transactions (debit > 0)."""
    ...

def calculate_net_cash_flow(statement_data: dict[str, Any]) -> dict[str, Any]:
    """Calculates total_credit - total_debit."""
    ...

def calculate_closing_balance(statement_data: dict[str, Any]) -> dict[str, Any]:
    """Retrieves closing balance from statement data and its source row from source_locations."""
    ...

def calculate_balance_reconciliation(statement_data: dict[str, Any]) -> dict[str, Any]:
    """Checks equation: opening_balance + total_credit - total_debit = closing_balance."""
    ...

def analyze_bank_statement(statement_data: dict[str, Any], workspace_id: str | None = None) -> dict[str, Any]:
    """Generates the full financial analysis envelope matching contracts/examples/financial-analysis.json."""
    ...
```

### How Prince's AI Tools Route Bank Queries:
In `backend/app/ai/tools.py`:
```python
from app.analysis.bank_kpis import (
    calculate_total_credit,
    calculate_total_debit,
    calculate_net_cash_flow,
    calculate_closing_balance,
)

# When user asks: "What is my net cash flow?"
result_metric = calculate_net_cash_flow(workspace_data)
# AI extracts: result_metric["value"], result_metric["unit"], result_metric["source_refs"]
```

---

## 4. Aarushi's Integration Guide: `backend/app/analysis/balance_sheet_kpis.py`

Prince's AI tool engine routes balance sheet analysis, liquidity questions, and reconciliation checks directly to your functions.

### Expected Function Signatures:
```python
from typing import Any

def calculate_working_capital(statement_data: dict[str, Any]) -> dict[str, Any]:
    """Calculates (Current Assets - Current Liabilities) multiplied by unit_scale.
    
    Formula:
        working_capital = (sum(current_assets) - sum(current_liabilities)) * unit_scale
    
    Rules:
        - unit_scale comes from statement_data["unit_scale"] (1 = units, 1000 = thousands, 100000 = lakhs, 10000000 = crores).
        - Value is converted to base currency (e.g., INR 7,000,000).
        - calculation_id: "balance_sheet.working_capital.v1"
        - Traceability: collects source_rows from unit_scale and all contributing asset/liability line items.
    """
    ...

def calculate_current_ratio(statement_data: dict[str, Any]) -> dict[str, Any]:
    """Calculates Current Assets / Current Liabilities in reported units.
    
    Formula:
        current_ratio = sum(current_assets) / sum(current_liabilities)
    
    Rules:
        - Do NOT apply unit_scale to the ratio itself. unit is "ratio".
        - Zero-Division Guard: If Current Liabilities == 0, return status="unavailable" with descriptive reason.
        - calculation_id: "balance_sheet.current_ratio.v1"
    """
    ...

def calculate_balance_difference(statement_data: dict[str, Any]) -> dict[str, Any]:
    """Calculates balance reconciliation discrepancy:
    difference = Total Assets - (Total Liabilities + Total Equity)
    
    Rules:
        - A difference of Decimal("0") indicates a perfectly balanced statement.
        - calculation_id: "balance_sheet.balance_difference.v1"
        - Traceability: points to source_rows of assets.total, liabilities.total, and equity.total.
    """
    ...

def analyze_balance_sheet(statement_data: dict[str, Any], workspace_id: str | None = None) -> dict[str, Any]:
    """Generates the full financial analysis envelope matching contracts/examples/balance-sheet-analysis.json."""
    ...
```

### Reference Fixtures for Aarushi:
- Input JSON structure: [`contracts/examples/balance-sheet.json`](../contracts/examples/balance-sheet.json)
- Expected Analysis Output: [`contracts/examples/balance-sheet-analysis.json`](../contracts/examples/balance-sheet-analysis.json)

---

## 5. Srujan's Integration Guide: `backend/app/ai/number_guard.py`

Srujan's module performs deterministic validation ensuring the LLM never hallucinates numbers or invents unverified claims.

### Implemented Function Signatures:
```python
from decimal import Decimal
from typing import Protocol, Sequence

class ToolEvidence(Protocol):
    value: object
    unit: str
    status: str

def verify_tool_results_text(text: str, tool_results: Sequence[ToolEvidence]) -> VerificationResult:
    """Checks all numeric tokens in AI text against available tool results and units.
    Returns VerificationResult with .valid (bool) and .issues (tuple of GuardIssue).
    """
    ...

def verify_numbers_in_text(ai_text: str, verified_numbers: list[Decimal]) -> bool:
    """Returns True if all numbers in ai_text are supported by verified_numbers."""
    ...
```

### How Prince's Chatbot & Summary Invoke the Number Guard:
In `backend/app/ai/chatbot.py`:
```python
from app.ai.number_guard import verify_tool_results_text

# Before returning the response to the user:
verification = verify_tool_results_text(response_text, executed_tool_results)
if not verification.valid:
    # 1. AI re-prompts the model with the exact issues to self-correct (bounded retry)
    # 2. If it still fails, raises HTTPException(status_code=502, detail={"code": "ai_validation_failed", ...})
```

---

## 6. Git Branching Recommendations

Please ensure all work is pushed on your own dedicated feature branches branched from `main`:

```bash
# For Rashi (Bank Statement Analytics):
git checkout main
git pull origin main
git checkout -b feature/bank-statement-analytics
# Work on backend/app/analysis/bank_kpis.py

# For Aarushi (Balance Sheet Analytics):
git checkout main
git pull origin main
git checkout -b feat/balance-sheet-analytics
# Work on backend/app/analysis/balance_sheet_kpis.py

# For Srujan (Number Guard):
git checkout main
git pull origin main
git checkout -b feat/number-guard
# Work on backend/app/ai/number_guard.py
```

---

## 7. Status & Testing Assistance

Prince's AI branch (`feat/ai-chat-assistant`) passes all 108 automated unit, database, and API tests. Fallback tools are in place so the system remains fully testable before all analysis PRs are merged.

If anyone wants help reviewing function parameters, testing fixtures, or setting up test cases, feel free to reach out anytime!
