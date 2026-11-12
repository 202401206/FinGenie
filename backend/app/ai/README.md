# AI Module Documentation

**Owner:** Prince Patel (AI 2: Conversational Assistant & AI Integration)  
**Track:** AI + Analysis Team  
**Status:** Implemented, Number Guard Verified & 100% Passing Tests (259 backend tests)  

---

## 1. Overview & Core Philosophy

The AI module powers **FinGenie's natural language understanding**, including the **AI Executive Summary** (`POST /api/workspaces/{id}/summary`) and the **Conversational Chatbot** (`POST /api/workspaces/{id}/chat`).

### The Golden Rule: The AI Never Makes Up a Number
In financial applications, LLMs cannot be trusted to perform raw arithmetic on transaction tables.  
To guarantee 100% mathematical accuracy and eliminate hallucinations:
1. **The LLM is forbidden from doing arithmetic.**
2. When answering financial questions, the LLM is given a menu of **deterministic Python calculation tools**.
3. The LLM decides *which* tool to call, our Python code executes the exact math locally using `Decimal` precision, and feeds the verified result back to the LLM.
4. Every draft response passes through **Srujan's Number Guard** before the user sees it.
5. If unverified numbers are detected, a bounded **2-attempt corrective retry loop** instructs the model to fix its response.
6. If the model persistently fails verification, an **HTTP 502 (`ai_validation_failed`)** error is returned so hallucinations never reach the user.
7. Every output includes full audit traceability: `calculation_ids` (formula versions), `source_refs` (exact source rows in the uploaded CSV/XLSX), and the mandatory legal disclaimer: *"This is not financial advice."*

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
├── number_guard.py            # Srujan's deterministic numeric verification guard (PR #4, merged)
├── guard_retry.py             # Number Guard verification, bounded retry loop & AIValidationError
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

### C. `number_guard.py` & `guard_retry.py` (Verification & Bounded Retry Loop)
Implements **Leader Review Point 2**: preventing ungrounded numbers from reaching the user.

* **Srujan's Number Guard (`number_guard.py`)**:
  * `verify_tool_results_text(text, tool_results)`: Structural check verifying that every number literal and currency unit in the prose matches an available `ToolResult`.
  * Regex validation supporting both Western (`125,000.00`) and Indian Lakhs/Crores (`1,25,000.00`) notation.
  * Enforces safe bullet dashes (`-`) and rejects detached negative signs (`- 5000`).
* **Retry Engine (`guard_retry.py`)**:
  * `verify_and_retry_text(initial_text, tool_results, messages, llm, max_retries=2)`:
    * Attempt 0: Checks the LLM's draft answer. If valid, returns immediately.
    * Attempts 1-2: If unverified numbers are found, appends a `SECURITY REJECTION` message citing the exact invalid tokens and re-prompts the model with greedy decoding (`temperature=0.0`).
    * If verification fails after 2 retries: raises `AIValidationError`.
* **API Route Mapping**:
  * Handled in `backend/app/api/routes/ai.py`:
  * Catches `AIValidationError` and returns **HTTP 502 Bad Gateway** with:
    ```json
    {
      "detail": {
        "code": "ai_validation_failed",
        "message": "Generated financial response failed numeric verification: ..."
      }
    }
    ```

---

### D. `summary.py` (AI Executive Summary Engine)
Powers `POST /api/workspaces/{id}/summary`.

* **Privacy-First Design:** Never transmits raw transaction lines to Groq. Computes verified aggregates locally (Total Deposits, Total Withdrawals, Net Flow, Closing Balance) and sends only those figures to Groq to generate a 2-sentence executive summary.
* **Balance Sheet Integrity Check:** If a balance sheet is un-reconciled ($\text{Assets} \neq \text{Liabilities} + \text{Equity}$), the engine halts AI generation and returns an explicit safety warning stating the exact discrepancy.
* **Guard Verification:** Runs `verify_and_retry_text()` on every summary before packaging into `SummaryResponse`.
* **Dual-Mode Execution:**
  * *Online:* Generates natural executive prose via Groq.
  * *Offline Fallback:* Automatically populates a clean deterministic template if the server is offline or lacks an API key.

---

### E. `chatbot.py` (Conversational Assistant)
Powers `POST /api/workspaces/{id}/chat`.

* **Multi-Turn Handshake Loop:**
  1. User asks question $\rightarrow$ Sent to Groq with `FINANCIAL_TOOLS`.
  2. If Groq requests tools $\rightarrow$ Python executes tools locally on workspace data.
  3. Tool output returned to Groq as a `tool` message.
  4. Groq synthesizes final grounded answer citing verified numbers.
  5. Bounded to 5 turns (`max_turns = 5`) to prevent infinite token loops.
* **Guard Verification:** Once `final_text` is generated, passes through `verify_and_retry_text()` before returning `ChatResponse`.
* **Refusal Guardrail (Rule 4):**
  * When asked about unsupported metrics (e.g. credit scores, cryptocurrency, stock predictions, or ROI), strictly refuses: *"I do not have a tool to calculate that"* and lists supported tools.
* **Authentication Security (Leader Point 1):**
  * Protected by FastAPI's `user: Annotated[CurrentUser, Depends(require_user)]`. Anonymous requests are rejected with **HTTP 401 Unauthorized**.

---

## 3. Team Member Allocation (Option A Standard)

| Teammate | Responsibility | Status |
|---|---|---|
| **Prince Patel** | AI 2: Conversational Assistant, AI Summary, Guard Integration, API Routes | Complete (PR #2) |
| **Srujan** | AI 1: Numeric Verification Guard (`number_guard.py`) | Merged (PR #4) |
| **Rashi Patel** | Analysis 1: Bank Statement Analytics (`bank_kpis.py`) | In Review (PR #5) |
| **Aarushi Shah** | Analysis 2: Balance Sheet Analytics (`balance_sheet_kpis.py`) | In Development |

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

All AI tests run offline using synthetic contract fixtures (`contracts/examples/`) and mock HTTP transports. No real API keys or internet connection are required for automated test runs:

```sh
cd backend
.\.venv\Scripts\Activate.ps1

# Run full backend test suite (259 tests passing)
python -m pytest tests/

# Run AI-specific tests
python -m pytest tests/ai/ tests/api/test_ai_routes.py -v

# Run Ruff linter and code formatting checks
python -m ruff check backend
python -m ruff format --check backend
```
