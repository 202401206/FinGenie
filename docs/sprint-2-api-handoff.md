# Sprint 2 API handoff

## Upload and show results

All requests use the signed-in user's access token. Use the returned workspace
ID for analysis and summary, and the document ID in any source references.

```javascript
const form = new FormData();
form.set("user_type", "business");
form.set("document_type", "balance_sheet");
form.set("file", file);

const response = await fetch("/api/upload", {
  method: "POST",
  headers: { Authorization: `Bearer ${accessToken}` },
  body: form,
});
```

Let the browser set the multipart Content-Type. A bank statement can use
personal or business. A balance sheet requires business. Both support CSV and
XLSX within the [upload limits](../backend/app/services/upload-validation.md).

| Request | Render |
| --- | --- |
| POST /api/upload | On 201, use the returned `workspace.id` and `document.id`. The document status is `parsed`. |
| GET /api/workspaces/{id}/analysis | On 200, show metrics, reliability, warnings, and source rows. A value of null is unavailable. Zero is a value. |
| POST /api/workspaces/{id}/summary | Send `{}`. On 200, show text, references, and the disclaimer. On 409, show why the summary is unavailable and keep the analysis visible if it loaded. |

The [API contract](../contracts/api/README.md) includes example responses and
links to the full analysis examples for both document types. The running app's
`/openapi.json` describes the implemented routes and error envelopes.

## Resume an interrupted upload

An uncertain upload can return this response with HTTP 503.

```json
{
  "detail": {
    "code": "reconciliation_required",
    "message": "Upload context could not be confirmed.",
    "attempt_id": "40000000-0000-4000-8000-000000000001"
  }
}
```

1. If the upload reply included an ID, get `/api/upload-attempts/{attempt_id}`.
   If the whole reply was lost, list `/api/upload-attempts?limit=50&offset=0` and
   show recent attempts so the user can choose the relevant one.
2. For an explicit recovery action, send `POST /api/upload-attempts/{attempt_id}/recover`
   with `Content-Type: application/json` and body `{}`.
3. A 200 `completed` response contains the original save receipt, including
   the workspace and document IDs. A 200 `cleaned` response means the original
   upload failed and cleanup finished. Its receipt is null.
4. After 401, sign in again and use the same attempt ID. For 503, show the
   pending status and keep the ID for a later recovery. A 409 `state_conflict`
   needs review. Missing or foreign attempts both return 404.

## Verify locally

With the [test dependencies](../supabase/tests/README.md) installed, run from
`backend` in PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts/verify_sprint2.py
.\.venv\Scripts\python.exe -m pytest -q verification/test_balance_parser_persistence.py verification/test_owned_analysis_api.py
```

A5 passed 1,281 backend tests, six explicit integration tests, and all eight SQL
suites. The catalog audit, API readiness, lint, formatting and dependency checks
also passed.

The suites use the real upload parser, API routes, and migrated local PostgreSQL
with simulated Auth, Storage and AI responses. They cover bank and balance
uploads, missing metadata, unreconciled figures, two-user isolation, and
recovery after a lost response.

## Development demo and review

Hosted verification is pending. With Shreyav, confirm the development project
and its applied migrations. Use two disposable users and synthetic files to
check upload, private source access, analysis, summary, and foreign-user denial.
Restart the backend and recover the original attempt with a fresh token. Record
safe IDs and statuses in the verification notes. Live AI requires the owner's
authorization and a configured development key.

Frontend should review status and error handling. AI + Analysis should review metric
availability and source references. See the [persistence verification notes](sprint-2-verification.md).
