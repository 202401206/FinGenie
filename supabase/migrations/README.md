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
