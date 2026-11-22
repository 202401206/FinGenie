# Bank-statement upload orchestration

## Status on 8 November 2026

Anshuman merged Dhaval's feature/backend-parsers branch in merge commit 4930cb1.
The production app now mounts POST /api/upload with the real CSV/XLSX parser.
Route tests use that production entry point and actual auth/repository/Storage
helper code, replacing only external Supabase HTTP with synthetic responses.

Hosted migrations, physical Storage operations and the live two-user browser
demo still require the lead's coordination. Those checks belong to the final
integration handoff.

## Interface and flow

The synchronous parse_bank_statement(content, *, file_kind, document_id)
function returns Dhaval's BankStatement model and raises
BankStatementParserError subclasses for supported parser failures. It runs in
a worker thread. Safe HTTP errors never include parser messages or raw rows.

UploadService uses the existing authenticated SourceUploadAccess,
ParsedDocumentRepository, UploadRecoveryService and WorkspaceRepository:

1. Authenticate before reading multipart input, then validate the file.
2. Generate workspace/document IDs and a Bank statement YYYY-MM-DD UTC name.
3. Parse the exact bounded bytes with the generated document UUID.
4. Validate the parsed result through the existing save model. Check the source
   document ID, 10,000 transaction limit and JSON serialization of all extra
   fields. model_dump(mode="python") preserves Decimal, dates and UUIDs.
5. Reserve metadata, upload the same original bytes, then atomically finalize.
6. Validate the receipt IDs and transaction count, then return the public
   workspace/document response with 201.

The contract response includes public workspace fields plus document id/status.
It excludes private paths, tokens and parsed financial contents.

## Resource rules and parser corrections

Intake caps source bytes at 5 MiB and expanded XLSX at 25 MiB. The ZIP member cap
is aligned with Dhaval's parser at 500. A separate 20,000 populated-record cap
per CSV/worksheet bounds structural inspection while allowing preambles,
footers and covers around the parser's 10,000 actual-transaction cap.
The default 50-column/cell cap remains. These are working development choices
for team review. Rows and columns are never silently truncated.

Integration tests found that the parser retained invalid transaction dates in
unmapped and could save a partial/empty statement. The CSV/XLSX date-error
handlers now raise when financial cells identify a transaction-shaped row,
including zero-valued cells and formulas. Padded nonfinancial metadata notes
remain preserved. This narrow parser correction needs Dhaval's review.

## Failures and recovery

Intake and parser rejection happen before writes. Expected parser failures
produce safe 422 statement_parse_failed responses.

After reservation starts, known failures invoke the lead's existing recovery
service once with the original attempt and validated data. SourceOutcomeUnknown
is handled before SourceUnavailable. There are no automatic write retries.

- Cleaned failures retain the original safe HTTP error.
- Pending recovery returns 401 or 503.
- Only a matching confirmed completed save can produce 201.
- If the reservation response was lost, read the owned workspace and verify
  its identity/context before constructing the success response.
- Malformed normal save receipts trigger recovery. Mismatched recovered
  receipts return a safe reconciliation error.

The existing helper owns source removal and metadata release. The orchestration
does not perform raw metadata deletes or separate transaction inserts.

Secure retention of full pending attempt/expected parsed context across request
termination or restart still requires the lead's operational design. There is
no durable reconciliation queue or public retry endpoint.

## Multipart and CORS

The registered factory requires exactly user_type, document_type and one file.
It rejects duplicates and extra fields. OpenAPI exposes those multipart fields.
File parsing uses pinned python-multipart==0.0.33.

Actual request bytes are bounded to the file limit plus 64 KiB overhead,
independent of Content-Length. Fields are limited to 64 KiB. Source bytes also
pass the stricter 5 MiB intake check. Temporary files close on success and
expected parser/size failures.

CORS permits GET and POST only for the existing configured origins.
The helper still accepts a custom UploadPolicy for unit tests. Increasing
intake limits does not override independent limits in the real parser.

## Evidence

Tests cover synthetic real CSV and generated XLSX files, the production route,
source byte/UUID preservation, exact Decimal values through the atomic-save
HTTP boundary, user-token separation, 10,000 transactions with metadata,
malformed dates/formulas, invalid layouts, write order and all recovery states.
Supabase HTTP is simulated. Hosted RLS/Storage and live demonstration remain
explicitly unverified.

Dependency reference:
https://pypi.org/project/python-multipart/0.0.33/
