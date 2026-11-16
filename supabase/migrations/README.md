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
