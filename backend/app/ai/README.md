# AI Module Documentation

**Owner:** Prince (AI 2: Conversational Assistant & AI Integration)  
**Track:** AI + Analysis Team  
**Status:** Implemented & Verified with 100% Passing Tests  

---

## 1. Overview & Core Philosophy

The AI module powers **FinGenie's natural language understanding**, including the **AI Executive Summary** (`POST /api/workspaces/{id}/summary`) and the **Conversational Chatbot** (`POST /api/workspaces/{id}/chat`).

### The Golden Rule: The AI Never Makes Up a Number
In financial systems, LLMs cannot be trusted to perform raw arithmetic on transaction tables.  
To guarantee 100% mathematical accuracy and zero hallucinations:
1. **The LLM is forbidden from doing arithmetic.**
2. When answering financial questions, the LLM is given a menu of **deterministic Python calculation tools**.
3. The LLM decides *which* tool to call, our Python code executes the exact math locally using `Decimal` precision, and feeds the verified result back to the LLM.
4. Every output includes full audit traceability: `calculation_ids` (formula versions), `source_refs` (exact source rows in the uploaded CSV/XLSX), and the legal disclaimer: *"This is not financial advice."*

---

## 2. Module Architecture & File Breakdown

```
backend/app/ai/
├── providers/
│   ├── __init__.py
│   └── groq_provider.py       # Groq LLM API adapter (async, tool calling, error handling)
├── tools.py                   # Tool registry, JSON schemas, execution engine, and source ref merger
├── summary.py                 # AI Executive Summary engine (Sprint 2 goal)
├── chatbot.py                 # Conversational Assistant multi-turn tool calling loop (Sprint 3 goal)
└── README.md                  # This documentation file
```

---

### A. `providers/groq_provider.py` (LLM Provider Adapter)
Implements the **Adapter Pattern** for Groq's OpenAI-compatible completions API (`https://api.groq.com/openai/v1`).

* **Key Classes:**
  * `GroqProvider`: Core async client with `generate(messages, tools, temperature=0.1)`.
  * `ToolCall`: Structured dataclass representing an LLM's request to execute a tool (`id`, `name`, `arguments`).
  * `GroqResponse`: Standardized response containing generated text, tool call requests, and finish reason.
* **Security & Reliability:**
  * Reads API key from `app.core.config.Settings.groq_api_key` wrapped in Pydantic's `SecretStr` to prevent token leakage in server logs.
  * Catches HTTP errors (429 Rate Limits, 503 Outages) and wraps them into `GroqAPIError` instead of letting raw crashes bubble up.
  * Dependency injection allows injecting `httpx.MockTransport` for instant, offline unit tests.

---

### B. `tools.py` (Tool Registry & Execution Engine)
Serves as the **bridge between the AI and the financial calculation engines**.

* **`FINANCIAL_TOOLS`**: The JSON schemas sent to Groq so the LLM knows which tools exist:
  * `bank_total_credit`: Total deposits / incoming money.
  * `bank_total_debit`: Total withdrawals / expenses.
  * `bank_net_cash_flow`: Total credits minus total debits.
  * `bank_closing_balance`: Closing balance at end of statement.
  * `balance_sheet_working_capital`: Current assets minus current liabilities (unit scaled).
  * `balance_sheet_current_ratio`: Liquidity ratio (current assets / current liabilities).
  * `balance_sheet_verify_reconciliation`: Verifies Assets = Liabilities + Equity.
* **`ToolResult` Dataclass**:
  Holds `value`, `unit`, `calculation_id`, `status`, `reason`, and `source_refs`. Uses `Decimal` to avoid floating-point rounding bugs.
* **`merge_source_refs()`**:
  Utility that deduplicates and sorts source row references across multiple tools so API responses remain clean and compact.

---

### C. `summary.py` (AI Executive Summary Engine)
Powers the **Sprint 2** endpoint `POST /api/workspaces/{id}/summary`.

* **Privacy-First Design:** Never transmits raw transaction lines to Groq. Computes verified aggregates locally (Total In, Total Out, Net Flow, Closing Balance) and sends only those 4 figures to Groq to generate a 2-sentence executive summary.
* **Balance Sheet Integrity Check:** If a balance sheet is un-reconciled ($\text{Assets} \neq \text{Liabilities} + \text{Equity}$), the engine halts AI generation and returns an explicit safety warning stating the exact discrepancy.
* **Dual-Mode Execution:**
  * *Online:* Generates natural executive prose via Groq.
  * *Offline Fallback:* Automatically populates a clean deterministic template if the server is offline or lacks an API key, guaranteeing the server never crashes.

---

### D. `chatbot.py` (Conversational Assistant)
Powers the **Sprint 3** endpoint `POST /api/workspaces/{id}/chat`.

* **Multi-Turn Handshake Loop:**
  1. User asks question $\rightarrow$ Sent to Groq with `FINANCIAL_TOOLS`.
  2. If Groq requests tools $\rightarrow$ Python executes tools locally on workspace data.
  3. Tool output returned to Groq as a `tool` message.
  4. Groq synthesizes final grounded answer citing verified numbers.
  5. Bounded to 3 turns (`max_turns = 3`) to prevent infinite loop token drain.
* **Scenarios Handled:**
  * *Financial Q&A:* Triggers tool execution, collects calculation IDs, and attaches row citations.
  * *Greetings / Capabilities:* Answers conversationally without running unnecessary tools (`calculation_ids: []`).
* **Prompt Injection Defense:** Strict system prompt forbids the LLM from inventing numbers or obeying user prompts that try to override calculation rules.

---

## 3. Integration Guide for Teammates

### For Aarushi (Bank Statement Analytics):
When you finish `backend/app/analysis/bank_kpis.py`:
1. In `backend/app/ai/tools.py`, find `_execute_bank_tool()`.
2. Replace the placeholder calculation with your functions:
   ```python
   from app.analysis.bank_kpis import (
       calculate_net_cash_flow,
       calculate_total_credit,
       calculate_total_debit,
   )

   # In _execute_bank_tool:
   if name == "bank_total_credit":
       return calculate_total_credit(data)
   ```

### For Rashi (Balance Sheet Analytics):
When you finish `backend/app/analysis/balance_sheet_kpis.py`:
1. In `backend/app/ai/tools.py`, find `_execute_balance_sheet_tool()`.
2. Delegate the tool calls to your functions in `app/analysis/balance_sheet_kpis.py`.

### For Srujan (Numeric Verification Guard):
When you finish `backend/app/ai/number_guard.py`:
1. In `backend/app/ai/chatbot.py`, import your verification function:
   ```python
   from app.ai.number_guard import verify_numbers_in_text
   ```
2. Call it before returning `ChatResponse`. If unverified numbers are found, trigger a retry prompt!

### For Team Leader / Backend (Routing):
To expose the endpoints in FastAPI, simply import `generate_summary` and `chat_with_workspace`:
```python
@router.post("/workspaces/{id}/summary", response_model=SummaryResponse)
async def get_summary(id: UUID, user: CurrentUser = Depends(require_user)):
    data = await get_workspace_data(id, user)
    return await generate_summary(data)


@router.post("/workspaces/{id}/chat", response_model=ChatResponse)
async def chat(
    id: UUID, request: ChatRequest, user: CurrentUser = Depends(require_user)
):
    data = await get_workspace_data(id, user)
    return await chat_with_workspace(request.message, data)
```

---

## 4. Configuration & Environment Variables

Add to `backend/.env` (defaults already set in `backend/.env.example`):
```properties
# Groq LLM Configuration (get free key at https://console.groq.com)
FINGENIE_GROQ_API_KEY=your_groq_api_key_here
FINGENIE_GROQ_MODEL=openai/gpt-oss-120b
FINGENIE_GROQ_BASE_URL=https://api.groq.com/openai/v1
```
*Note: If `FINGENIE_GROQ_API_KEY` is omitted, the app operates seamlessly in offline fallback mode without crashing.*

---

## 5. Running Tests

All AI tests run offline using synthetic contract fixtures (`contracts/examples/`) and mock HTTP transports. No real API keys or internet connection are required:

```sh
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ai/
python -m ruff check app/ai/ tests/ai/
```
