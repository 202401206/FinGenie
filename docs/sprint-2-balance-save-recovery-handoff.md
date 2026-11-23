# Balance save and recovery: handoff for Anshuman

Balance save was implemented in `da8b707`. Balance recovery is the follow-up on
`feature/backend-sprint-2-persistence`. Merge reviewed dependencies into
`feature/backend-sprint-2` before enabling business balance uploads. Apply the
reviewed migrations to the target database before exercising a live workflow.
This handoff is not evidence of hosted deployment or a merged recovery PR.

## Dependency and method contracts

```python
from typing import Annotated
from fastapi import Depends

from app.db.dependencies import get_parsed_document_repository
from app.db.repositories.parsed_documents import ParsedDocumentRepository
from app.services.source_dependencies import get_upload_recovery_service
from app.services.upload_recovery import UploadRecoveryService
```

Use these existing route dependencies:

```python
save_repository: Annotated[
    ParsedDocumentRepository, Depends(get_parsed_document_repository)
]
recovery_service: Annotated[
    UploadRecoveryService, Depends(get_upload_recovery_service)
]
```

Inside the async service, unchanged calls are:

```python
receipt = await save_repository.finalize(reservation, parsed_data)
result = await recovery_service.recover(original_attempt, parsed_data)
```

`reservation` is `SourceReservation`. `original_attempt` is its server-generated
`SourceAttempt`, retained from before reservation. `parsed_data` is the validated
dictionary in reported units; use `model_dump(mode="python")` for parser models
so Decimal values survive. Never regenerate IDs or reinterpret source data after
a failure. Neither method belongs in a shell command.

No Python method signature, receipt field, recovery-result field or exception
type changes in this recovery slice. No new package dependency is needed.

## Save receipt

`app.db.parsed_models.ParsedSaveReceipt` retains:

| Field | Type/value |
| --- | --- |
| workspace_id | Original workspace UUID |
| document_id | Original document UUID |
| status | parsed |
| transaction_count | Strict integer; exactly 0 for balance sheets |

Bank receipts still contain the validated transaction count. A mismatched ID,
nonzero balance count, boolean count or malformed success receipt is an unknown
outcome, not proof that the save rolled back.

Save dispatch is internal: bank → finalize_bank_statement, balance →
finalize_balance_sheet. Balance validation and recovery share the same normalized
stored contract, preserving unknown metadata, source locations, prior periods and
exact amounts. Do not introduce a fake transactions array or apply unit scale in
persistence/recovery. Analysis owns scaling and financial reconciliation.

## Recovery results and errors

`app.services.recovery_models.RecoveryResult` is unchanged:

| status | receipt | reason | Caller behavior |
| --- | --- | --- | --- |
| completed | Confirmed ParsedSaveReceipt | None | Return confirmed success; preserve snapshot and source |
| cleaned | None | None | Original upload failed and was cleaned; do not return upload success |
| pending | None | auth_required | Reauthenticate the same owner; retain context |
| pending | None | reconciliation_required | Saved state is uncertain; do not remove source or retry finalization blindly |
| pending | None | cleanup_required | Source/removal/release is unconfirmed; retain IDs/context and retry recovery explicitly |
| pending | None | state_conflict | Preserve data/source for investigation; do not overwrite or delete |

Repository exceptions from `app.services.source_errors` remain:

- ParsedDocumentRejected: invalid expected parsed data; safe 422 at the API boundary.
- SourceUnauthorized: caller token rejected.
- SourceConflict: unsafe state/dependency conflict.
- SourceUnavailable: dependency/configuration failure.
- SourceOutcomeUnknown("recovery"): lost/unusable reconciliation or release result.
  This inherits SourceUnavailable and is converted by the service to pending.

Foreign `attempt.user_id` compared with the verified repository user raises
ValueError before network access. Unsupported future document types still use
`app.db.errors.UnsupportedDocumentType`. Save-side WorkspaceNotFound behavior is
unchanged. The service converts expected auth/dependency/conflict errors into the
pending reasons above, but does not hide invalid parser/context programming errors
as a successful cleanup.

Direct repository methods stay `begin(attempt, parsed_data)` and `release(attempt)`.
Bank begin uses the old RPC; balance begin uses begin_balance_sheet_recovery with
the same original workspace/document/extension/expected-JSON inputs. Both reuse
release_failed_upload only after source removal.

## Reconciliation guarantees

The balance RPC runs as the authenticated caller with RLS and an empty search
path. It uses existing account/workspace locks and locks the owned workspace and
document in the established order. It never accepts an owner ID as authority.

Completed balance recovery requires:

- The original business balance workspace/document and canonical source path.
- Complete expected JSON equality, including nulls, prior periods and traceability.
- Matching currency and null bank-period columns.
- Zero transaction rows, registered source and no cancellation marker.

Any disagreement is preserved as a conflict. A missing registered source does not
justify deleting a completed parsed snapshot. An uncertain RPC result causes no
cleanup. Only an unfinished/absent owned attempt reaches cancellation and Storage
removal. Release independently verifies source absence and failed/empty metadata.

Other users cannot read/change the owner's records or remove their source. As in
bank recovery, guessed foreign UUIDs are absent in the caller's own namespace;
clearing that namespace does not expose the original owner's state. Future public
attempt endpoints must first load an owned stored attempt, returning the agreed
404 for missing/foreign attempts, rather than accepting a fabricated SourceAttempt
from request JSON.

## Existing settings/upload-generation dependency

This branch also contains settings commit `4a03af5`. Use the current
get_source_upload_access dependency and preserve `access.upload_generation` on the
SourceAttempt before processing. Keep it on that same attempt through recovery;
do not refresh it mid-attempt to bypass deletion. The shared source lock rejects
recovery while financial-data deletion is pending. This slice does not change the
generation contract added by settings.

## Integration order and scope

1. Merge the reviewed owned reader (already delivered through PR #11).
2. Merge balance save `da8b707` and this recovery slice into integration. Review
   settings `4a03af5` too if using this combined branch as the PR head.
3. Verify Dhaval's parser output matches the agreed stored contract and original
   source UUID/rows, preserving Decimal and null metadata.
4. Extend upload dispatch and the upload service's bank-only validation/count
   assumptions. Use the unchanged 201 public upload response; balance receipt count
   is zero. Do not enable the route just because low-level save tests pass.
5. Keep the durable upload journal and public attempt APIs in A4/P4. Retain current
   original context securely until then; this service alone does not persist it
   across a process restart. The settings deletion journal is a different feature.

## Verified checks and limits

The combined backend suite passes 1,030 tests. There are 33 new Python recovery
tests; all seven embedded SQL suites pass. Checks cover lost finalization and
reconciliation responses, unfinished cleanup, cleanup failure, empty receipts,
repeats, stray rows/JSON, metadata/source conflicts, exact values and foreign-user
isolation. Existing bank and settings regressions pass. Lint, formatting and
dependency checks pass, with one existing TestClient deprecation warning.

SQL runs against embedded PostgreSQL/RLS; Auth/Storage HTTP and bytes are synthetic.
No hosted migration, actual Storage operation, independent-session lock contention
or public balance parser/upload demo was performed. Deployment/two-user integration
verification remains a reviewed step.
