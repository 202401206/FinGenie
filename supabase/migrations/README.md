# Database migrations - Backend team

`20261025120342_initial_backend_foundation.sql` creates the three application tables,
their constraints/indexes, ownership policies, and the private source-file bucket.
It is already applied to the team's hosted development project. Its version matches
the hosted migration history; do not rerun it there manually.

Use the pinned Supabase CLI 2.122.0 and create future files with
`supabase migration new <name>`. Inspect command help before using other CLI
operations. Never edit a migration already applied to a shared database; add a
new migration. Keep credentials and financial documents out of migration files.

Run `../tests/ownership.sql` against the migrated database to exercise ownership
and constraints with synthetic data inside a transaction that is rolled back.
See `../../docs/supabase-setup.md` for configuration, verification and local-runtime
limitations. Review SQL and shared data contracts with the affected team members.

`20261030202630_reserve_source_upload.sql` adds an authenticated, security-invoker
RPC that creates workspace/document metadata atomically before a Storage upload.
It derives ownership from `auth.uid()` and narrows function execution to
`authenticated`; the existing table RLS policies remain active. It adds no parsed
transaction writes or file bytes. This migration is prepared locally and has not
been applied to the hosted project as part of this work.

Run `../tests/source_reservations.sql` after migrations as postgres. It exercises
successful reservations, cross-user visibility, missing identity, anonymous
execution restrictions, duplicate IDs and rollback on a late document failure.
Both SQL test scripts roll back their synthetic fixture rows.

`20261101181352_finalize_bank_statement.sql` adds the bank-statement finalization
RPC. It locks an owned, pending document and saves parsed JSON, metadata and all
transaction rows in one transaction. It requires a registered private source,
rejects repeats/failed documents/existing rows, and grants execution only to
authenticated callers. It uses invoker privileges and retains the existing RLS.
This migration is also prepared locally and has not been deployed by this work.

Run `../tests/parsed_documents.sql` after all migrations to test atomic rollback,
source/state preconditions, exact money and owner isolation. All three SQL test
scripts roll back their synthetic rows; they do not upload real Storage bytes.

`20261116201152_finalize_balance_sheet.sql` adds a separate authenticated,
security-invoker RPC for business balance snapshots. It uses the existing shared
upload lock and cancellation guard, locks the owned parent/document, checks the
registered canonical source, validates JSON, and saves parsed status/currency/JSON
without transaction inserts. Reporting date and unit scale remain in JSON; bank
period columns stay null. Existing bank functions and RLS policies are unchanged.

This migration was generated with the pinned CLI and verified locally. It has
not been applied to the hosted development project by this work. Run
`../tests/balance_documents.sql` after all migrations for atomicity, exact values,
readiness/source constraints, ownership and function privilege checks. Do not
enable public balance uploads until the parser, dispatch and recovery support
are integrated and reviewed.

`20261117182410_user_settings_and_data_deletion.sql` adds owner-scoped preferences,
durable deletion jobs/source manifests and upload generations. New RPCs run with
caller privileges and a locked account scope. Partial preference writes preserve
omitted fields. Deletion progress survives requests/restarts and does not store
tokens or parsed financial payloads. Completion requires confirmed source absence
and removes transactions/documents/workspaces while retaining Auth and preferences.

The migration also extends the shared source lock with the account deletion
barrier and introduces generation-aware reservation. The original seven-argument
reservation RPC remains a generation-zero wrapper; new app requests capture the
current generation before processing. This prevents a late, unreserved old upload
from recreating financial data after deletion. Existing bank/balance save RPCs
continue to use the shared lock.

This migration is prepared and tested locally, not deployed by this work. See
`../../docs/settings-api-handoff.md` for frontend retry semantics and
`../tests/settings.sql` for ownership, retries, trigger guards and privilege checks.
Deploy the application and migration together after review; older applications
that keep using generation zero cannot upload for an owner after their first
financial-data deletion.

`20261117191222_balance_sheet_recovery.sql` adds the authenticated invoker
`begin_balance_sheet_recovery(uuid,uuid,text,jsonb)` RPC. It uses the current shared
source/account locks and cancellation markers, preserves verified completed
snapshots with zero transactions, and marks only unfinished attempts for cleanup.
The original bank recovery and generic failed-source release functions are unchanged.
This is a locally tested migration, not a hosted deployment. Run
`../tests/balance_recovery.sql` after all migrations; the complete runner now has
the suites described below. Public recovery routes remain separate A4 work.

`20261120100100_durable_upload_attempts.sql` adds the owner-RLS upload journal,
immutable validated recovery context, safe paginated summary RPC and
revision-checked reconciliation/settlement. Completed/cleaned states need actual
saved-data or cancellation/absence evidence; a stale completed marker never
authorizes cleanup. Needs-review context is preserved. Functions use invoker
privileges and existing account/source lock order.

The same migration includes upload-attempt payloads in Settings deletion,
including journal-only uploads and outdated deletion-key protection. Journal
context is retained until confirmed financial-data deletion; separate cancellation
IDs/generations remain afterward. No tokens, automatic worker or public attempt
HTTP routes are introduced. The production bank upload now requires this migration
before source reservation. It was generated with the pinned CLI and tested locally,
not deployed by this work. See `../../docs/sprint-2-upload-attempt-handoff.md` and
`../tests/upload_attempts.sql`. The complete SQL runner now has eight suites.
