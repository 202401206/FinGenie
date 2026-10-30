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
