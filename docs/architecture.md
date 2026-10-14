# Architecture

The frontend is a React/Vite browser app. A single FastAPI backend contains all
Python code, including analysis and AI. Modules are folders with a focused purpose,
not independently deployed services.

Current flow: `React title page` and, separately, `GET /api/health -> health JSON`.
The health response is a liveness check: it does not promise database readiness.

Planned flow:

```text
Browser -> Supabase Auth (signup/login)
Browser + access token -> FastAPI -> ownership / file checks
  -> parser -> validated standardized JSON -> private storage / PostgreSQL
  -> deterministic Python analysis -> dashboards
  -> validated calculations / tools -> AI -> numeric guard -> summary / chat
```

The API verifies the Supabase access token and workspace owner before reading
or writing private data. CORS only controls which browsers may call an API; it
does not authenticate a user. Current CORS permits GET from localhost/127.0.0.1
on port 5173. Extend allowed methods when implementing writes. Local development
uses bearer tokens, so credentialed cookies are not enabled.

## Module boundaries

- `api/`: HTTP routing, request/response models and status codes.
- `core/`: settings; security and exception handling will be added here later.
- `schemas/`: Pydantic models for shared Python data validation. Only basic enums,
  a document context model and the health response exist now.
- `services/`: later coordinates parsing, persistence, analysis and AI.
- `parsers/`: later turns CSV/XLSX into standardized JSON. Check inputs before
  parsing and validate outputs afterward. Never silently discard unknown fields.
- `db/repositories/`: future database queries; no generic repository framework.
- `analysis/`: pure Python functions receiving validated data and returning results.
  No imports from API, database, services, Supabase or LLM providers. Tests use
  synthetic contract fixtures without credentials or an HTTP server.
- `ai/`: summary, chat, calculation tools, provider adapters and numeric validation.
  Calls analysis functions, never invents or recalculates financial results in prose.

Planned module names (`upload.py`, `security.py`, `bank_kpis.py`, `summary.py`, etc.)
are recorded in directory READMEs rather than created as empty Python files.
Only implemented routes are registered. FastAPI's standard `/docs`, `/redoc` and
`/openapi.json` are also available; they show the implemented API only.

## Financial integrity

Preserve `source_row` and `unmapped`. Every result needs source document, sheet
where applicable, original rows and calculation identifier. Amounts need a known
currency; no implicit currency conversion. Python calculations should use `Decimal`
for money, with rounding agreed per metric. Convert balance-sheet `unit_scale`
to base currency exactly once. JSON examples preserve the PDF's numeric fields.

A failed Assets = Liabilities + Equity check must flag an unreliable result.
Do not silently fill missing numbers with zero. Division by zero returns an
unavailable metric with a reason. Bank projections use deterministic averages or
trends and require roughly three months of history; the precise coverage rule is
still to be agreed. Single balance-sheet projections are outside V1.

AI receives validated JSON and calculations, preferably aggregates. Numeric claims
must match tool results with source references; unsupported numeric claims are
rejected and retried. Each future AI response includes the PDF's financial-advice
disclaimer. No LLM calls or numeric guard are implemented yet.

## Scope and privacy

CSV/XLSX only. PDF/scanned uploads, income/cash-flow statements, payments, third-party
integrations and an admin panel are outside V1. Multi-file workspaces and PDF export
are stretch goals. One file per workspace is the V1 plan.

Never log financial data, account numbers, tokens, prompts containing private data
or complete provider responses. Keep raw files private; use synthetic public fixtures.
Server-only Supabase secrets and Groq keys must never use a `VITE_` variable.
Ollama local experimentation and Groq deployment are intended later choices.
