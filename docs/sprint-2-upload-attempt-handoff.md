# Durable upload attempts: P4 handoff

P4 adds the owned recovery journal and internal interfaces for Anshuman's A4
routes. Migration: `20261120100100_durable_upload_attempts.sql`. Apply all earlier
persistence/settings/recovery migrations first. This change prepares and tests
local SQL; it does not deploy a hosted migration.

## Current integration

The mounted bank upload path now follows:

1. Verify Auth and capture the upload generation.
2. Validate/read the bounded file and parse it using the real bank parser.
3. Validate parsed data and confirm journal creation.
4. Reserve the original workspace/document, upload the private source, finalize.
5. Verify the saved state in SQL before marking the journal completed.

An unknown journal-creation response stops before step 4. A lost save/settlement
response preserves the original IDs and source for follow-up. Parsing failures
create no journal or source records. The public upload request and 201 response
remain unchanged. UploadProcessingError now has an internal optional attempt_id;
the existing HTTP error presenter still returns code/message only. A4 can expose
the safe attempt ID deliberately without serializing the private SourceAttempt.

Balance journal/recovery support is implemented and tested. Public business
balance upload dispatch remains Anshuman's A2 dependency work. The current
UploadService parser/receipt validation still handles bank statements; extend it
deliberately for A2 rather than adding fake transactions to balance JSON.

No public upload-attempt routes are added by P4. A4 owns their routing, HTTP
response models and status mapping.

## Imports and authenticated dependency

```python
from typing import Annotated
from fastapi import Depends

from app.services.source_dependencies import get_upload_attempt_service
from app.services.upload_attempts import UploadAttemptService
from app.db.repositories.upload_attempts import UploadAttemptNotFound

Attempts = Annotated[UploadAttemptService, Depends(get_upload_attempt_service)]
```

The dependency uses the existing request-local HTTP client, verified user UUID and
original Bearer token. There is no elevated key, shared-client auth mutation or
stored token. After reauthentication, create the dependency with the same owner's
fresh credentials and recover by attempt ID.

## Interfaces

All calls below run inside async Python code, not a shell.

```python
# Internal upload workflow: after parsing/validation, before any source writes.
# Generate once on the server and keep it if the response is lost.
from uuid import uuid4
attempt_id = uuid4()
summary = await attempts.prepare(original_attempt, parsed_data, attempt_id=attempt_id)

# The existing upload service already calls these for production bank uploads.
# Do not double-journal it in an HTTP wrapper.
summary = await attempts.confirm_completed(attempt_id)

# A4 status discovery, including pending and terminal attempts.
page = await attempts.journal.list_attempts(limit=50, offset=0)
summary = await attempts.journal.get_summary(attempt_id)

# A4 manual action: loads the owned immutable context and checks saved state.
result = await attempts.recover(attempt_id)
```

`prepare` returns only a pending UploadAttemptSummary after creation is confirmed.
It accepts an identical pending creation with the same IDs/context as idempotent;
different context, a terminal record or invalidated generation conflicts. Never
continue reservation after an unknown result. `confirm_completed` is for the
initial successful upload at revision zero. For retries or a lost confirmation,
use recover, which loads the current revision and rechecks current evidence.

`list_attempts` returns the existing `Page[UploadAttemptSummary]` dataclass:
items, limit, offset, total. Bounds: limit 1..100, offset >=0, strict integers.
Order is created_at DESC, id DESC. It includes completed/cleaned/needs_review
records so a wholly lost response can still be discovered. It does not silently
filter out terminal attempts.

`get_summary` is safe to present using a dedicated HTTP response model:

| Field | Type |
| --- | --- |
| attempt_id, workspace_id, document_id | UUID |
| document_type | bank_statement or balance_sheet |
| status | pending, completed, cleaned, needs_review |
| last_error_code | null or the safe recovery reason below |
| receipt | ParsedSaveReceipt only for completed, otherwise null |
| created_at, updated_at | Timezone-aware datetime |

There is no original filename, owner ID, source path, expected JSON, credential or
internal revision in this summary. A stored completed summary reports the last
verified event and its timestamp; a fresh recover checks current saved state.
Analysis must still use the owned parsed-document reader for current data.

`journal.get(attempt_id)` returns StoredUploadAttempt containing summary, original
SourceAttempt, validated parsed_data and revision. This is internal recovery data,
not a route response. Do not return it, log it or accept replacement context from
an HTTP caller. Exact Decimal decoding happens before Pydantic validation.

## Result and receipt compatibility

`attempts.recover` returns the unchanged RecoveryResult:

| Result | Meaning and recommended A4 response |
| --- | --- |
| completed + receipt | Current saved snapshot/source matches; 200 completed. |
| cleaned | Unfinished original upload cancelled and source/metadata absence verified; 200 cleaned, never 201 upload success. |
| pending + auth_required | Credentials failed during reconciliation/cleanup; 401 and reauthenticate the same owner. |
| pending + reconciliation_required | Unknown dependency/write outcome or concurrent revision change; 503, retain original attempt ID. |
| pending + cleanup_required | Source/metadata cleanup not confirmed; 503, explicit resume later. |
| pending + state_conflict | Journal becomes needs_review; 409 state_conflict, preserve data/source/context. |

ParsedSaveReceipt fields and finalize(reservation, parsed_data) are unchanged:
workspace_id, document_id, status="parsed", transaction_count. Balance count is
always zero. No bank transaction array is added to balance JSON.

Needs-review records stay needs_review under ordinary recovery. Resolving a
conflict is a deliberate review task, not a force-cleanup flag. A previously
completed journal is never sufficient authority to clean a now-conflicting source.
Cleaned records are also rechecked; unexpected surviving/reappearing state is
preserved for review.

## Exceptions for A4

| Exception | Meaning / mapping |
| --- | --- |
| UploadAttemptNotFound | Missing and foreign IDs deliberately match; 404. |
| SourceUnauthorized | Request JWT rejected, including before loading context; 401. |
| SourceOutcomeUnknown("journal") | Journal request/reply could not be confirmed; subclass of SourceUnavailable; 503. |
| SourceUnavailable | Malformed/inaccessible dependency or stored context; 503. |
| SourceConflict | Generation, cancellation, identity or revision conflicts; 409, preserve state. |
| ParsedDocumentRejected | Invalid create-time parsed context; 422, no source writes. |
| ValueError from pagination / owner mismatch | Validate query bounds at the route; owner mismatch is an internal misuse, never a request-selected identity. |

The service converts failures after loading/reconciling into conservative
RecoveryResult pending outcomes where possible. Failure to load an owned attempt
can still raise an exception. Do not catch these and manufacture a completed or
empty successful response.

Recommended A4 routes remain GET /api/upload-attempts, GET
/api/upload-attempts/{attempt_id}, POST /api/upload-attempts/{attempt_id}/recover.
The recover body should allow no context overrides. Use the original current
request's authenticated dependency; never accept owner/path/expected_json from
the client. Add safe attempt_id to relevant upload error details in A4.

## Integrity, concurrency and retention

The owner-RLS table uses immutable context and independent attempt IDs. It has
no workspace FK because it must exist before workspace reservation and survive
failed metadata cleanup. Original owner/workspace/document IDs, file kind,
filename, name, generation and parsed JSON cannot be changed after insertion.

Invoking create or settling state uses the same account-before-source locks as
existing uploads/deletion. Revision checks stop an older recovery reply from
overwriting newer journal evidence. Concurrent calls may return pending and must
be explicitly retried; they do not restart uploads.

Completed updates check actual parsed state/source through the existing bank or
balance recovery SQL. Cleaned updates require original cancellation evidence and
absence of the workspace/document/source. The table trigger enforces this even
when an owner calls the table API directly. Functions are security invoker with
an empty search_path; grants and RLS remain owner scoped.

Retention policy: keep immutable expected JSON/context for future verification
until the owner deletes financial data. There is no automatic expiry or background
cleanup. Financial-data deletion includes journal-only attempts, retains separate
cancellation IDs/generations, and purges journal rows in the confirmed deletion
transaction. A completed deletion key also rejects newly journaled data, even
when no workspace/source exists yet. Auth/preferences remain intact.

## Validation and deployment boundary

Tests exercise the real repository/service/SQL/RLS path with synthetic Auth and
Storage HTTP. Cases include bank/balance lost finalization, lost journal writes,
restart with a new service, repeated recovery, cleanup failure, conflicting saved
state, stale completed markers, foreign/missing IDs, exact Decimal extras,
overlapping recovery settlement, expired/fresh credentials and data deletion.
SQL tests cover direct table writes, immutable context, anonymous/foreign denial,
unverified terminal-state rejection and revision guards.

Run backend pytest, Ruff lint/format and pip check; run npm test --prefix
supabase/tests for all eight SQL suites. Embedded PostgreSQL and controlled
request interleaving do not establish hosted Storage/Auth or independent database
session contention. Those development-project checks remain P5 after A2/A4 meet.

Integrate this commit into feature/backend-sprint-2 alongside the earlier save,
settings and both-type recovery commits. Preserve Anshuman's later upload dispatch
changes when resolving overlaps. Deploy reviewed migrations before running the
new production upload path against a hosted project.
