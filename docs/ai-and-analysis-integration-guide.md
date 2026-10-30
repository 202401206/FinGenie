# FinGenie AI + Analysis Team: Integration Guide & Interface Contract

**Document Owner:** Prince Patel (AI 2: Conversational Assistant & AI Integration)  
**Collaborators:** Aarushi Shah (Bank Analytics), Rashi (Balance Sheet Analytics), Srujan (Number Guard)  
**Target Milestone:** Sprint 2 & Sprint 3 Integration  
**Reference Contracts:** [`contracts/README.md`](../contracts/README.md) and [`contracts/api/README.md`](../contracts/api/README.md)

---

## 1. Team Ownership & Architecture Boundary

To ensure clean separation of concerns, zero code conflicts, and clear individual accountability for evaluation, our team responsibilities are mapped as follows:

| Team Member | Component / Track | Target File Path | Primary Responsibility |
| :--- | :--- | :--- | :--- |
| **Aarushi Shah** | Bank Statement Analytics | `backend/app/analysis/bank_kpis.py` | Deterministic calculations for deposits, debits, cash flow, and closing balance. |
| **Rashi** | Balance Sheet Analytics | `backend/app/analysis/balance_sheet_kpis.py` | Deterministic calculations for working capital, liquidity ratio, and Assets = Liab + Equity reconciliation. |
| **Srujan** | Numeric Verification Guard | `backend/app/ai/number_guard.py` | Post-generation safety filter validating that all numbers in AI text match verified calculation results. |
| **Prince Patel** | AI Integration & Assistant | `backend/app/ai/` & `backend/app/api/routes/ai.py` | LLM provider adapter, deterministic tool routing, executive summary engine, multi-turn conversational loop, and API endpoints. |

---

## 2. Shared Financial Data Conventions

Per the team contract in [`contracts/README.md`](../contracts/README.md), all calculation and safety code must adhere to:
1. **Exact Precision (`Decimal`):** Never use binary Python `float` for monetary math. Always use `from decimal import Decimal`.
2. **1-Based Source Rows:** `source_row` indices must correspond to the original 1-based spreadsheet row or CSV record (e.g., Row 6 to Row 205). Never fabricate row numbers (e.g., `i + 1`).
3. **Preserve Missing Data:** Never fabricate a `0` or default `"INR"` if a document is missing amounts, closing balance, or currency. Report missing fields cleanly with `status="unavailable"`.

---

## 3. Aarushi's Integration Guide: `backend/app/analysis/bank_kpis.py`

Prince's AI tool engine (`backend/app/ai/tools.py`) will route bank queries directly to your functions.

### Expected Function Signatures:
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

### How Prince's AI Tools Will Call Your Code:
In `backend/app/ai/tools.py`:
```python
from app.analysis.bank_kpis import (
    calculate_total_credit,
    calculate_total_debit,
    calculate_net_cash_flow,
    get_closing_balance,
)

# When user asks: "How much did I spend this month?"
# Prince's tool calls: calculate_total_debit(workspace_data)
```

---

## 4. Rashi's Integration Guide: `backend/app/analysis/balance_sheet_kpis.py`

Prince's AI tool engine will route balance sheet analysis and reconciliation checks directly to your functions.

### Expected Function Signatures:
```python
from decimal import Decimal
from typing import Any

def calculate_working_capital(data: dict[str, Any]) -> Decimal | None:
    """(Current Assets - Current Liabilities) multiplied by unit_scale.
    Returns None if currency, scale, or line items are missing.
    """
    ...

def calculate_current_ratio(data: dict[str, Any]) -> Decimal | None:
    """Current Assets / Current Liabilities.
    Returns None if liabilities are zero (zero-division guard) or data is missing.
    """
    ...

def verify_reconciliation(data: dict[str, Any]) -> Decimal | None:
    """Calculates discrepancy: Total Assets - (Total Liabilities + Total Equity).
    Returns Decimal('0') if balanced; discrepancy magnitude otherwise.
    """
    ...
```

### How Prince's AI Tools Will Call Your Code:
In `backend/app/ai/tools.py`:
```python
from app.analysis.balance_sheet_kpis import (
    calculate_working_capital,
    calculate_current_ratio,
    verify_reconciliation,
)

# When user asks: "Is my balance sheet balanced?"
# Prince's tool calls: verify_reconciliation(workspace_data)
```

---

## 5. Srujan's Integration Guide: `backend/app/ai/number_guard.py`

The Team Leader's review on PR #2 specifically highlighted the need for this safety guard:
> *"The prompt tells the model not to invent numbers, but nothing checks its answer. A mocked response claiming a closing balance of INR 999999999 was returned unchanged even though the fixture says INR 12500... Validate financial claims against calculation results... return 502 ai_validation_failed if validation fails."*

### Expected Function Signature:
```python
from decimal import Decimal

def verify_numbers_in_text(
    ai_text: str,
    verified_numbers: list[Decimal],
) -> bool:
    """Scans ai_text for numeric claims.
    Returns True if every financial number in the text matches an allowed verified number.
    Returns False if an unverified/hallucinated number (e.g., 999999999) is detected.
    """
    ...
```

### How Prince's Chatbot & Summary Will Invoke Your Guard:
In `backend/app/ai/chatbot.py` and `summary.py`:
```python
from app.ai.number_guard import verify_numbers_in_text

# After Groq generates an answer:
is_valid = verify_numbers_in_text(ai_response_text, allowed_numbers=[res.value for res in executed_tools])

if not is_valid:
    # 1. AI re-prompts the model once to self-correct
    # 2. If it still hallucinates, raises HTTPException(status_code=502, detail={"code": "ai_validation_failed", ...})
```

---

## 6. Git Branching Recommendations

To avoid stepping on each other's work, please create your own feature branches from `main`:

```bash
# For Aarushi:
git checkout main
git pull origin main
git checkout -b feat/bank-analytics
# Work on backend/app/analysis/bank_kpis.py
git push -u origin feat/bank-analytics

# For Rashi:
git checkout main
git pull origin main
git checkout -b feat/balance-sheet-analytics
# Work on backend/app/analysis/balance_sheet_kpis.py
git push -u origin feat/balance-sheet-analytics

# For Srujan:
git checkout main
git pull origin main
git checkout -b feat/number-guard
# Work on backend/app/ai/number_guard.py
git push -u origin feat/number-guard
```

---

## 7. Status & Assistance

Prince's AI branch (`feat/ai-chat-assistant`) currently contains **fallback calculation engines** and passes all 34 automated unit and API tests. Your integration will replace those fallback calculations with the official team analysis layer.

If anyone wants help reviewing function parameters, testing fixtures, or setting up test cases, feel free to reach out anytime!
