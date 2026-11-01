# Atomic bank-statement persistence

`ParsedDocumentRepository.finalize(reservation, parsed_data)` saves a bank
statement's JSON, document metadata and transaction rows through one RPC. It is an
internal building block, not an upload endpoint or a parser.

## Using the repository

Inject `get_parsed_document_repository` from `app.db.dependencies` with FastAPI
`Depends`. It verifies the caller and uses the same request-local client and
original access token as the existing source helpers. The current source-helper
bundle and read-repository interfaces are unchanged.

The upload service's intended order is:

1. Verify the user and generate a `SourceAttempt` on the backend.
2. Read within the agreed bound, validate the file and parse it with the attempt's
   document UUID. Neither parsing nor file intake is implemented by this repository.
3. Reserve metadata, then upload the source using the existing helpers.
4. Pass the reservation and parsed dictionary to `finalize`.
5. Map the returned IDs/status/count to the agreed public response. Only return 201
   after the whole workflow succeeds.

If the parser returns a Pydantic model, pass `model_dump(mode="python")` so money
stays Decimal. If loading JSON, decode monetary numbers with Decimal rather than
float. The existing contract fixture is used in tests; no new parser interface or
public API response fields are introduced.

## Validation and exact JSON

`app/db/parsed_models.py` checks data at the save boundary. It validates required
bank-statement fields, finite amounts, nonnegative debit/credit, positive integer
source rows, matching source document UUID and ordered optional period dates.
Unknown optional metadata is represented by null, not an invented default.
Extra fields, unmapped values and source locations are preserved.

These are persistence validation models, not Dhaval's parser implementation. The
parser remains responsible for supported bank layouts, byte/content checks,
original row references and normalization. Core fields are normalized to their
validated types before saving; unknown fields must also be JSON-serializable.

Money can be supplied as Decimal, integer or exact decimal text; Python float and
bool inputs are rejected for amount fields. `simplejson==3.20.2` sends Decimal as
JSON numbers without `float()` conversion. Dates/UUIDs are encoded explicitly.
The resulting JSON is checked for invalid constants, including in unknown fields.
This does not change the existing read/API serialization contract.

## The database operation

Apply reviewed migrations in order before using the new RPC against Supabase.
`20261101181352_finalize_bank_statement.sql` is prepared locally and not deployed
by this change. It requires both earlier migrations and an already registered
private source object.

The security-invoker function:

- derives identity from `auth.uid()` and keeps table RLS active;
- locks the owned document row while checking/changing its state;
- hides absent and unowned documents behind the same not-found result;
- requires an uploaded, unparsed bank statement with no pre-existing transaction rows;
- checks Storage metadata for the document's exact private path;
- validates the required JSON shape and transaction fields;
- updates parsed JSON/currency/period/status and inserts all transactions together;
- rolls the entire operation back on a malformed or invalid later row.

Repeated finalization returns a conflict, even with identical data. It does not
append duplicates, replace a parsed document, or claim an automatic idempotent
retry succeeded. Row locking serializes cooperating finalization calls for a
document. Direct owners' database/Storage permissions are not immutable archival
guarantees, and this change does not add new deletion protections or versioning.

The Storage check is a database metadata check. Actual file upload/removal stays
in the Storage API. It is not a distributed transaction protecting bytes against
every concurrent authorized deletion. The final workflow must coordinate cleanup
so it cannot run against an active or successful save.

## Outcomes and failure handling

The receipt contains `workspace_id`, `document_id`, `status="parsed"` and the saved
transaction count. The repository checks those values against the reservation and
validated input before reporting success.

| Signal | Meaning / suggested API translation |
| --- | --- |
| `WorkspaceNotFound` | Absent/unowned workspace-document pair, 404 |
| `UnsupportedDocumentType` | This repository handles bank statements, 409 |
| `ParsedDocumentRejected` | Invalid parsed data, safe 422 |
| `SourceUnauthorized` | Token rejected, safe 401 with Bearer challenge |
| `SourceConflict` | Source/state/repeat-save conflict, safe 409 |
| `SourceUnavailable` | Other dependency/configuration failure, safe 503 |
| `SourceOutcomeUnknown("finalization")` | Save may have committed; reconcile the same owned IDs before any retry or cleanup |

The database's `PT404` means the owned record was not found. An upstream 404 for a
missing RPC is a configuration failure instead. Neither path returns upstream SQL
details. A timeout, 5xx or invalid success receipt is not evidence of rollback.
There are no automatic retries or Storage deletions in this repository.

Full failed-state handling, metadata retention/release, owned reconciliation reads
and the complete parser/upload/read integration remain the final planned work
package. Do not delete a source just because finalization returned a conflict or
an uncertain response; a previous request may already have completed.

## Checks

- The Python suite has 160 passing tests, including 37 new save-boundary cases.
- Existing authentication, read and Storage tests remain unchanged and passing.
- `supabase/tests/parsed_documents.sql` checks rollback after a later invalid row,
  ownership, missing source files, repeats, existing rows, failed status, exact
  amounts, null metadata and preserved content.
- All three SQL suites pass in the local embedded PostgreSQL harness with minimal
  Supabase auth/storage scaffolding. Their fixtures roll back.

No hosted database change, real Storage file operation, full Docker replay or
end-to-end browser upload was performed for this change.
