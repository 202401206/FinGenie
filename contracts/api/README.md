# V1 endpoint contract plan

Only health is implemented. All other payloads/status codes below are proposed
conventions for review, not fake routes or promises of an existing API. Endpoint
names and sprint placement come from the user's request; the PDF specifies the
upload fields and overall workflow.

| Sprint | Method | Path | Success |
| --- | --- | --- | --- |
| Initial | GET | `/api/health` | 200 |
| 1 | POST | `/api/upload` | 201 |
| 1 | GET | `/api/workspaces` | 200 |
| 1 | GET | `/api/workspaces/{id}` | 200 |
| 1 | GET | `/api/workspaces/{id}/transactions` | 200 |
| 2 | GET | `/api/workspaces/{id}/analysis` | 200 |
| 2 | POST | `/api/workspaces/{id}/summary` | 200 |
| 3 | POST | `/api/workspaces/{id}/chat` | 200 |
| 3 | GET | `/api/workspaces/{id}/projections` | 200 |

## Common planned rules

Health is public. Every other endpoint requires
`Authorization: Bearer <Supabase access token>`. Verify token signature, expiry,
issuer/audience as appropriate; derive the user from the verified token. All
workspace routes enforce ownership, including transactions, AI and projections.
Uploads/listing are scoped to the authenticated user. A nonexistent or unowned
workspace returns 404 to avoid disclosing another user's data.

Supabase Auth handles signup/login: no duplicate password authentication endpoints.
JSON endpoints use `Content-Type: application/json`; upload uses multipart.
List endpoints accept `limit` (default 50, range 1-100) and `offset` (default 0,
nonnegative). Stable ordering: workspaces by `created_at DESC, id DESC`, transactions
by original `source_row ASC, id ASC`. Pagination and IDs are proposed conventions.
`{id}` is a workspace UUID. Responses expose no private storage paths or keys.

## Initial: health

`GET /api/health`, no body, no auth. Current response:

```json
{"status": "ok", "service": "fingenie-api"}
```

This is a liveness check only. It does not connect to any external service.

## Sprint 1: upload and workspaces

`POST /api/upload`: multipart fields `user_type` (`personal`/`business`),
`document_type` (`bank_statement`/`balance_sheet`), `file` (CSV/XLSX bytes).
No client-provided owner ID. The browser sets the multipart boundary; callers
using FormData must not manually set `Content-Type`.

Validate allowed combinations, file type/content, required columns and eventual
size limit; then parse and validate standardized JSON. Proposed synchronous flow:
return 201 only after parsing and persistence succeed. Do not imply background
processing or add a queue. Never accept PDF or arbitrary renamed content.

Example 201:

```json
{
  "workspace": {
    "id": "20000000-0000-4000-8000-000000000001",
    "name": "Synthetic January statement",
    "user_type": "personal",
    "document_type": "bank_statement",
    "created_at": "2026-01-31T12:00:00Z"
  },
  "document": {
    "id": "10000000-0000-4000-8000-000000000001",
    "status": "parsed"
  }
}
```

Name generation/defaults remain a Backend/UI agreement; `name` is not an additional
required upload field. Do not calculate summaries or call an LLM during upload.

`GET /api/workspaces?limit=50&offset=0`: no body; current user's workspaces only.
Each item has the same fields as the `workspace` object above. Example 200:

```json
{
  "items": [
    {
      "id": "20000000-0000-4000-8000-000000000001",
      "name": "Synthetic January statement",
      "user_type": "personal",
      "document_type": "bank_statement",
      "created_at": "2026-01-31T12:00:00Z"
    }
  ],
  "limit": 50,
  "offset": 0,
  "total": 1
}
```

`GET /api/workspaces/{id}`: no body. Example 200:

```json
{
  "workspace": {
    "id": "20000000-0000-4000-8000-000000000001",
    "name": "Synthetic January statement",
    "user_type": "personal",
    "document_type": "bank_statement",
    "created_at": "2026-01-31T12:00:00Z"
  },
  "documents": [
    {
      "id": "10000000-0000-4000-8000-000000000001",
      "status": "parsed",
      "original_filename": "synthetic-bank.csv",
      "currency": "INR",
      "period_start": "2026-01-01",
      "period_end": "2026-01-31"
    }
  ]
}
```

An array anticipates the PDF's potential multi-file extension; V1 holds one file.
Balance-sheet period dates may be null; reporting date remains in parsed JSON.
Sanitize any displayed original filename. Do not expose raw financial content in lists.

`GET /api/workspaces/{id}/transactions?limit=50&offset=0`: no body. Example 200:

```json
{
  "items": [
    {
      "id": "30000000-0000-4000-8000-000000000001",
      "document_id": "10000000-0000-4000-8000-000000000001",
      "date": "2026-01-05",
      "description": "Synthetic salary",
      "debit": 0,
      "credit": 5000,
      "balance": 15000,
      "source_row": 6
    }
  ],
  "limit": 50,
  "offset": 0,
  "total": 1
}
```

This one-item response illustrates the shape independently of the three-row fixture.
Balance-sheet workspaces return 409 `unsupported_document_type`. Date/category
filters can be proposed when their UI is designed; none are promised here.

## Sprint 2: analysis and summary

`GET /api/workspaces/{id}/analysis`: no body. 200 body matches
[bank analysis](../examples/financial-analysis.json) or
[balance-sheet analysis](../examples/balance-sheet-analysis.json).
Only Python functions compute KPIs. No database access inside deterministic analysis.
Unreliable parsed data produces explicit reliability/warnings and unavailable
metrics where necessary. Unparsed/failed workspaces return 409 `document_not_ready`.

`POST /api/workspaces/{id}/summary`: JSON request `{}`. Returns a nonstreaming,
validated summary of the workspace's calculated results, never the raw file.
Example 200:

```json
{
  "text": "Calculated net cash flow is INR 2500 for this statement period.",
  "calculation_ids": ["bank.net_cash_flow.v1"],
  "source_refs": [
    {
      "document_id": "10000000-0000-4000-8000-000000000001",
      "sheet_name": null,
      "source_rows": [6, 7, 8],
      "field_paths": ["transactions[0].credit", "transactions[1].debit", "transactions[2].debit"]
    }
  ],
  "disclaimer": "This is not financial advice."
}
```

Always display the disclaimer last. Numeric content must pass the future guard
against referenced calculation outputs; references alone do not establish validity.
Do not generate an authoritative summary when required inputs are unreliable.

## Sprint 3: chat and projections

`POST /api/workspaces/{id}/chat`: request
`{"message":"What is my net cash flow?"}` (nonempty text; proposed maximum 2000
characters). Initial proposed contract is one question/answer per request, no
stored conversation history or streaming. A future history design needs review.
200 body uses the same `text`, `calculation_ids`, `source_refs`, `disclaimer` shape
as summary. Call calculation tools; reject/retry unsupported numbers. Bound retries;
if validation cannot succeed return 502 `ai_validation_failed` with no unvalidated
answer. Do not trust instructions embedded in document cells or user messages to
override the calculation/ownership boundaries.

`GET /api/workspaces/{id}/projections?months=3`: no body. Proposed `months` default
3, range 1-6. Bank statements only; deterministic averages/trend, no LLM.
The PDF requires roughly 3+ months of historical data; the exact coverage test
must be agreed before implementation. This one-month fixture is insufficient.

Proposed 200 eligible response fields (no eligible historical fixture is included):

| Field | Format |
| --- | --- |
| `workspace_id` | UUID string |
| `currency` | Currency code, e.g. `INR` |
| `method` | Agreed algorithm name, e.g. `monthly_average_net_flow` |
| `calculation_id` | Reviewed definition/version, e.g. `bank.balance_projection.v1` |
| `history_months` | Number of months satisfying the agreed coverage rule |
| `points` | Array of `{month: "YYYY-MM", expected_balance: number}` in base currency, one per requested month |
| `assumptions` | Array of strings explaining the model's assumptions |
| `source_refs` | Same document/sheet/rows/field-path shape as analysis; include closing balance and all contributing history |

No arithmetic/model implementation is included. Assumptions, historical coverage
and source references must be returned. Balance sheets return 409
`unsupported_document_type`; insufficient bank history returns 409
`insufficient_history` as illustrated below. Do not return invented projection
points. Runway output/zero-spend handling can be added after agreeing its definition.

## Proposed error format

Use FastAPI's `detail` wrapper. Expected domain errors may have an object:

```json
{
  "detail": {
    "code": "insufficient_history",
    "message": "Bank projections need roughly three months of history."
  }
}
```

FastAPI's automatic 422 validation errors retain their normal array shape:

```json
{"detail":[{"loc":["body","message"],"msg":"Field required","type":"missing"}]}
```

Clients must handle domain objects, validation arrays and default string `detail`
responses. Do not log validation payloads containing private financial content.

| Status | Planned cases |
| --- | --- |
| 401 | Missing/invalid/expired Supabase token |
| 404 | Workspace absent or not owned by caller |
| 409 | Not parsed yet, unsupported analysis type, insufficient history |
| 413 | File exceeds the team-agreed size limit |
| 415 | Unsupported file type |
| 422 | Invalid fields/combination/document content or schema validation error |
| 429 | Per-user limits, especially AI/upload; exact limits TBD |
| 502/503 | AI validation/provider failure or temporarily unavailable dependency |

Unexpected errors must not expose stack traces, tokens, account numbers or raw
rows to clients. The foundation does not implement domain error handling, auth,
rate limits or provider integrations.
