# Sprint 1 API handoff

## Current status

Uploads and the three workspace routes are implemented. Both parser layouts work
with CSV and XLSX. The local checks passed with 474 tests and all four SQL suites.
Lint, formatting and dependency checks also passed.

The hosted Supabase demo and teammate reviews are still pending.

## Using the API

Protected routes require Authorization: Bearer <user access token>.
The backend gets the owner from the verified token.

| Request | Result |
| --- | --- |
| POST /api/upload | Creates a workspace and returns its public fields plus document id/status |
| GET /api/workspaces | Lists the signed-in user's workspaces |
| GET /api/workspaces/{id} | Returns workspace details and document metadata |
| GET /api/workspaces/{id}/transactions | Returns a page of transactions |

For upload, send FormData with user_type, document_type and one file.
user_type can be personal or business. document_type is bank_statement.
Balance-sheet uploads return 422 for now. Let the browser set the multipart
Content-Type and boundary.

A successful upload returns 201 after the save is confirmed. The response
examples are in [the API contract](../contracts/api/README.md).
Private paths, tokens and parsed statement contents are excluded.

List responses contain items, limit, offset and total. Limit defaults to 50
and accepts 1–100. Offset starts at zero. A page past the end keeps the actual
total even when items is empty.

Workspaces sort by created_at DESC, id DESC. Transactions sort by source_row ASC,
id ASC. Unknown optional metadata stays null. Money is sent as JSON numbers,
with Decimal precision preserved in the backend. Frontend code should use these
values for display and leave financial calculations to the backend.

## File rules

- CSV must use UTF-8, optionally with a BOM.
- CSV/XLSX must match one of the two supported layouts in the
  [parser README](../backend/app/parsers/README.md).
- Maximum source size is 5 MiB. Expanded XLSX content is limited to 25 MiB.
- Maximum ZIP entries is 500. Columns/populated cells per row are limited to 50.
- Intake allows 20,000 populated records/worksheet rows, including metadata.
  The parser and save boundary allow at most 10,000 actual transactions.
- The multipart request budget adds 64 KiB for framing and fields.

These are the current development limits for team review. The parser checks
headers, dates and financial values. The intake helper checks bytes, encoding,
file type and XLSX container safety. Invalid financial-row dates now reject the
upload, while nonfinancial notes remain in unmapped. Dhaval should review this fix.

## Errors the frontend needs to handle

| Status | Meaning |
| --- | --- |
| 401 | Missing or rejected token |
| 404 | Workspace missing or owned by someone else |
| 409 | Unsupported transaction document type or upload conflict |
| 413 | File/request too large |
| 415 | Unsupported extension or MIME mismatch |
| 422 | Invalid fields, file contents, layout or processing limits |
| 503 | Dependency unavailable or recovery pending |

Expected errors contain detail.code and detail.message. FastAPI's query/UUID
validation returns a detail array. Handle both shapes.

After an uncertain upload failure, check the outcome before retrying. The save
may have completed even if its response was lost.

## Running the checks

From the repository root:

    npm.cmd ci --prefix supabase/tests --ignore-scripts
    npm.cmd test --prefix supabase/tests

Then from backend:

    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe -m ruff check app tests
    .\.venv\Scripts\python.exe -m ruff format --check app tests

The tests cover both layouts/formats, upload and readback, user isolation, exact
money values, and recovery after lost responses. They run the actual API, parser
and persistence code against embedded PostgreSQL with real migrations and RLS.
Auth and Storage HTTP are simulated. Hosted Auth and physical Storage still need
the separate demo below.

## Before the final PR

With Shreyav, use a development Supabase project and synthetic statements:

1. Confirm the reviewed migrations are applied in order.
2. Configure the backend locally without sharing credentials.
3. Upload as user A, then check workspace listing/details and saved transactions.
4. Confirm the private source file exists. As user B, check that A's workspace
   is absent from the list and its details/transactions return 404.
5. Agree test-data cleanup and follow-up for uploads with pending recovery.

The lead also needs to settle how pending attempt context is retained across
request termination or server restarts before accepting real records.

Dhaval reviews the parser changes, Frontend reviews payloads/errors, and Shreyav
reviews persistence/recovery and confirms the PR base. Anshuman opens the PR
after the Sprint 1 checks and handoff.
