# Upload orchestration and parser handoff

## Status on 8 November 2026

The upload service and router factory are tested against a controlled parser.
The repository checkout and GitHub main tree still contain parser scaffolding.
The current GitHub branch list has no feature/backend-parsers branch.

POST /api/upload remains unmounted until Dhaval's real parser is supplied.
There is no production parser fallback. This is a tested integration checkpoint,
with real parser and hosted verification outstanding.

## Interfaces

UploadService composes the existing bounded intake, SourceUploadAccess,
ParsedDocumentRepository, UploadRecoveryService and WorkspaceRepository.
It does not implement database queries, source cleanup primitives or bank parsing.

The supplied synchronous parser receives content bytes, file_kind as csv/xlsx,
and a generated document_id UUID. It returns a Pydantic model. Run it in a worker
thread so parsing does not occupy the application's async event loop.

The proposed signature is:

    parse_bank_statement(content: bytes, *, file_kind: str, document_id: UUID)

BankParseError is the integration boundary for an expected parser rejection.
Once Dhaval supplies his implementation, adapt his actual model/error types at
this boundary instead of changing or duplicating his parser. Confirm this
interface with him before activation.

## Successful flow

1. Existing dependencies verify the caller and carry the original token.
2. Manually parse the multipart form after authentication, then validate the file.
3. Generate SourceAttempt IDs and a Bank statement YYYY-MM-DD name using UTC.
4. Call the parser with the exact bounded bytes and generated source document ID.
5. Validate through the existing parsed-save model, matching the source ID and
   10,000 transaction limit. Check all extra fields are finite, serializable JSON.
   model_dump(mode="python") keeps Decimal, dates and UUIDs intact.
6. Reserve metadata, upload the same original bytes, then atomically finalize.
7. Validate the receipt against the generated IDs and transaction count, then
   return the public workspace/document response with status 201.

The public response excludes source paths, tokens and parsed financial contents.
The service creates no owner ID from client input.

## Failures and recovery

Intake or parser rejection happens before database or Storage changes. Safe
errors are returned without parser messages or validation payloads.

After reservation starts, known failures call the existing recovery helper once
with the same attempt and validated parsed data. SourceOutcomeUnknown is handled
before SourceUnavailable. There are no automatic write retries.

- Cleaned failures retain the original safe HTTP failure.
- Pending recovery returns safe 401 or 503 and never reports creation.
- A confirmed completed recovery can return 201 with the matching receipt.
- If the reservation response was lost, read owned workspace metadata and check
  it matches the attempt before constructing the public success response.
- An invalid normal save receipt triggers reconciliation. A mismatched recovered
  receipt produces a safe reconciliation error rather than success.

The existing recovery service owns the database decision, source removal and
metadata release. This orchestration never deletes metadata directly.

Pending errors retain the attempt in the service exception for an authorized
caller. The HTTP response contains only safe error fields. Secure retention of
complete attempt/expected parsed context across request termination or a server
restart still needs the lead's operational design before a hosted demo with
financial data. No durable reconciliation queue or public retry endpoint is added.

## Multipart and CORS

create_upload_router(real_parser) constructs the future route. It reuses the
existing request-scoped dependencies and requires exactly user_type,
document_type and one file, rejecting duplicates and extra fields.

Multipart parsing uses the new pinned python-multipart==0.0.33 dependency.
The router reads no body before authentication. Its ASGI receive guard counts
actual body bytes regardless of Content-Length and allows the configured file
limit plus 64 KiB for framing and fields. Multipart fields are bounded to 64 KiB.
File content still passes the stricter 5 MiB intake limit. Parser-limit failures
close temporary multipart files and are mapped to safe errors.

CORS permits GET and POST for the existing configured origins. Activating the
factory still requires a real parser import and router registration in
app/api/router.py, plus reviewed shared migrations and team interface agreement.

## Checks and outstanding work

Tests cover call order, exact bytes and source IDs, Decimal preservation,
pre-write validation, each write-stage failure, cleanup/unknown/completed
recovery, malformed receipts, auth, multipart limits, invalid fields and files,
temporary-file cleanup and CORS.

These tests use synthetic parser results and controlled writers. They do not
prove compatibility with Dhaval's real bank models, deployed migrations,
physical Storage operations or the live two-user upload/read demonstration.

Before calling milestone 4 complete, obtain the parser branch/function/error
contract, adapt and test it, mount the route, and coordinate migration/recovery
readiness with the lead. Milestone 5 adds the real cross-component evidence.

Dependency reference:
https://pypi.org/project/python-multipart/0.0.33/
