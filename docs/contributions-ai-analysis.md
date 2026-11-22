# FinGenie - Official Course Project Contribution Document
**DA-IICT | IT314: Software Engineering (Autumn 2026-27)**  
**Course Instructor:** Prof. Saurabh Tiwari  
**Submission Deadline:** 03/12/2026 by 05:00 PM (FB-1 Letterbox / Office Submission)  
**Track:** AI Assistant & Financial Analysis Module  
**Repository:** `https://github.com/202401206/FinGenie`  

---

## 1. Group Information & Verification Statement

This document certifies the individual engineering contributions of the **AI Assistant & Financial Analytics Track** for the semester course project **FinGenie**. All contributions detailed herein are permanently recorded in the project's Git commit history, pull requests (PRs), code reviews, and automated test suites.

| Student Name | Student ID | Academic Email | GitHub Username | Assigned Track Role |
| :--- | :---: | :--- | :--- | :--- |
| **Prince Patel** | **202401206** | `202401206@dau.ac.in` | `Prince-Patel84` / `202401206` | AI Engine Lead & System Architect |
| **Rashi Patel** | **202401154** | `202401154@dau.ac.in` | `RKPatel9701` | Bank Statement Analytics Engineer |
| **Aarushi Shah** | **202401193** | `202401193@dau.ac.in` | `aarushi-shah617` | Balance Sheet Analytics Engineer |
| **S-Srujan** | **202401185** | `202401185@dau.ac.in` | `S-Srujan` | AI Safety & Verification Engineer |

---

## 2. Granular Individual Contribution Breakdown

### 2.1 Prince Patel (Student ID: 202401206)
- **Primary Role:** AI Module Lead, LLM System Architect & Testing Lead
- **Owned Source Files:**
  - `backend/app/ai/chatbot.py`: Orchestrated conversational function-calling loop, prompt construction, multi-turn reasoning (up to 5 turns), truncation safety guard, and offline deterministic fallback.
  - `backend/app/ai/summary.py`: Built executive summary synthesis for bank statements and corporate balance sheets.
  - `backend/app/ai/providers/groq_provider.py`: Engineered OpenAI-compatible Groq LLM client with async HTTP connection pooling, token truncation detection, and fault-tolerant error translation.
  - `backend/app/api/routes/ai.py`: FastAPI endpoints for conversational chat (`POST /api/workspaces/{id}/chat`) and summaries (`POST /api/workspaces/{id}/summary`).
  - `backend/tests/ai/test_white_box_coverage.py`: Authored comprehensive white-box test suite achieving 100% statement coverage on core AI modules.
- **Pull Requests Authored:**
  - **PR #2:** `feat(ai): conversational financial assistant, AI summary engine, and Groq integration` (Merged to `main`).
  - **PR #7:** `test(ai): add white-box testing suite, coverage report, and achieve 99.5% coverage` (Open on `main`).
- **Code Metrics:** ~1,850 Lines of Python & Test Code | 18+ Git Commits.
- **Viva Defense Topics Prepared:**
  1. *How does the Groq tool-calling loop prevent hallucination?* (The LLM never computes numbers; it only outputs JSON function call requests. All numbers are computed locally via Decimal Python functions).
  2. *How is truncation handled?* (When `response.finish_reason == "length"`, the system intercepts the truncated output and falls back to deterministic template synthesis, preventing corrupted numbers).
  3. *Why use Decimal over float?* (Floating-point representation creates binary approximation errors like `0.1 + 0.2 = 0.30000000000000004`, which is unacceptable in financial ledgers).

---

### 2.2 Rashi Patel (Student ID: 202401154)
- **Primary Role:** Bank Statement Analytics Engineer
- **Owned Source Files:**
  - `backend/app/analysis/bank_kpis.py`: Engineered the pure, deterministic bank statement calculation engine.
  - Built total credits calculation (`calculate_total_credits`), total debits calculation (`calculate_total_debits`), net cash flow (`calculate_net_cash_flow`), and chronological balance verification (`calculate_closing_balance`).
  - Enforced strict negative-debit magnitude normalization (`abs(amount)`) and arbitrary-precision Decimal arithmetic.
  - Attached formula versioning (`calculation_id`) and cell-level source row traceability (`source_refs`) to every computed metric.
  - `backend/tests/analysis/test_bank_kpis.py`: Authored 120+ unit tests covering edge-case bank layouts, blank movements, multiline CSVs, and date parsing.
- **Pull Requests Authored:**
  - **PR #5:** `Add bank statement analytics and tests` (Merged to `main`).
- **Code Metrics:** ~1,450 Lines of Python & Test Code | 12+ Git Commits.
- **Viva Defense Topics Prepared:**
  1. *How do you ensure audit traceability?* (Each `ToolResult` carries a `SourceRef` object specifying the document ID, sheet name, and exact spreadsheet row numbers where the raw transactions originated).
  2. *How are negative debits handled?* (Accounting standards require debit totals to be expressed as positive magnitudes. The engine strictly rejects malformed negative debits and normalizes values).

---

### 2.3 Aarushi Shah (Student ID: 202401193)
- **Primary Role:** Balance Sheet Analytics Engineer
- **Owned Source Files:**
  - `backend/app/analysis/balance_sheet_kpis.py`: Engineered the corporate balance sheet analysis and liquidity ratio engine.
  - Implemented the fundamental accounting reconciliation check:
    $$\Delta = \text{Total Assets} - (\text{Total Liabilities} + \text{Total Equity})$$
  - Designed the three-state reliability classifier: `valid` ($\Delta = 0$), `unreliable` ($\Delta \neq 0$), and `insufficient_data` (missing totals).
  - Implemented Working Capital ($\text{Current Assets} - \text{Current Liabilities}$) with `unit_scale` scaling.
  - Implemented Current Ratio with defensive division-by-zero guards for zero-liability corporations.
  - `backend/tests/analysis/test_balance_sheet_kpis.py`: Authored comprehensive test suite verifying balance sheet envelopes, reconciliation alerts, and invalid dictionary sanitization.
- **Pull Requests Authored:**
  - **PR #6:** `feat(analysis): implement deterministic balance sheet analytics engine and tests` (Merged to `main`).
- **Code Metrics:** ~1,100 Lines of Python & Test Code | 10+ Git Commits.
- **Viva Defense Topics Prepared:**
  1. *What happens when a balance sheet doesn't balance?* (The engine sets `status = "unreliable"`, records the exact discrepancy $\Delta$, and halts automatic executive synthesis to warn the user that the accounting data is flawed).
  2. *How is division by zero avoided in Current Ratio?* (When Current Liabilities equal zero, the engine returns `status = "unavailable"` with reason `"Current liabilities are zero"` rather than raising an uncaught `ZeroDivisionError`).

---

### 2.4 S-Srujan (Student ID: 202401185)
- **Primary Role:** AI Safety & Verification Engineer
- **Owned Source Files:**
  - `backend/app/ai/number_guard.py`: Engineered the regex-based numeric extraction and validation engine.
  - Extracted integers, decimals, currency symbols (`$`, `₹`, `€`, `INR`, `USD`), and percentages from natural language.
  - Implemented cryptographic numeric grounding: verifying that every generated number exists in the pool of executed tool results within an epsilon tolerance of $0.001$.
  - `backend/app/ai/guard_retry.py`: Designed the bounded corrective retry loop that intercepts ungrounded numbers and re-prompts the LLM with exact discrepancy details.
  - `backend/tests/ai/test_number_guard.py`: Authored 140+ unit tests covering edge numeric formats, currency prefixes, tolerance bounds, and sign consistency.
- **Pull Requests Authored:**
  - **PR #4:** `feat(ai): add numeric verification guard for AI financial answers` (Merged to `main`).
- **Code Metrics:** ~950 Lines of Python & Test Code | 9+ Git Commits.
- **Viva Defense Topics Prepared:**
  1. *How does Number Guard detect hallucinations?* (It parses all numeric tokens from the LLM's text and compares them against the exact Decimal values produced by local deterministic tools. Any ungrounded number triggers a verification failure).
  2. *How does the bounded retry loop work?* (If verification fails, the system re-prompts the model up to 2 times, feeding back the exact unauthorized token. If the model cannot correct it, the system raises `AIValidationError` to prevent misleading the user).

---

## 3. Evidence of Teamwork, Code Reviews & Collaboration

The AI + Analysis team conducted rigorous peer code reviews on every pull request prior to merging into `main`:
1. **Review of PR #2 (AI Conversational Engine):** Reviewed by Aarushi Shah and S-Srujan; verified tool execution boundaries and offline fallback.
2. **Review of PR #4 (Number Guard):** Reviewed by Prince Patel and Rashi Patel; validated token extraction on Indian currency notation (Lakhs / Crores).
3. **Review of PR #5 (Bank Analytics):** Reviewed by Aarushi Shah and S-Srujan; validated date formatting and running balance checks.
4. **Review of PR #6 (Balance Sheet Analytics):** Reviewed by Prince Patel and Rashi Patel; validated `unit_scale` propagation.
5. **Review of PR #7 (White-Box Testing):** Reviewed by S-Srujan, who requested and verified the inclusion of the provider response truncation guard (`finish_reason == "length"`).

---

## 4. Submission Sign-Off

We hereby certify that all information submitted in this document is accurate, reflects our genuine work, and is fully verifiable in the project's Git commit log and GitHub repository.

- **Prince Patel (202401206)** — AI Engine Lead
- **Rashi Patel (202401154)** — Bank Statement Analytics Engineer
- **Aarushi Shah (202401193)** — Balance Sheet Analytics Engineer
- **S-Srujan (202401185)** — AI Safety & Verification Engineer
