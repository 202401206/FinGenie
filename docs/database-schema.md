# Planned Supabase schema

Design only: no tables, SQL migrations, storage buckets or policies are created.
The first three tables and their fields come from the brainstorming PDF (page 4).
Types, constraints, indexes and access policies below are proposed implementation
conventions requiring Backend review.

| Table | Planned fields |
| --- | --- |
| `workspaces` | `id uuid PK`, `user_id uuid FK auth.users(id)`, `user_type text`, `document_type text`, `name text`, `created_at timestamptz` |
| `documents` | `id uuid PK`, `workspace_id uuid FK workspaces(id)`, `file_path text`, `original_filename text`, `currency text`, `period_start date nullable`, `period_end date nullable`, `status text`, `parsed_json jsonb nullable`, `created_at timestamptz` |
| `transactions` | `id uuid PK`, `document_id uuid FK documents(id)`, `date date`, `description text`, `debit numeric`, `credit numeric`, `balance numeric`, `source_row integer` |

Relationships: user -> many workspaces -> documents -> transactions. V1 accepts one
document per workspace; the relationship permits more later. Balance sheets stay
in `documents.parsed_json`; their reporting date and scale are preserved there.
Document status is `uploaded`, `parsed` or `failed`. Do not invent additional states
until an actual workflow requires them.

Proposed constraints: allowed user/document enum values, personal users cannot
select balance sheets, nonnegative debit/credit, positive source rows. Generate IDs
and timestamps server-side. Proposed indexes: `workspaces(user_id)`,
`documents(workspace_id)`, `transactions(document_id, date)`.
Use exact PostgreSQL `numeric` for money, not floating point. Nullable metadata
means unknown, not zero or an empty date. Do not deduplicate transactions solely on
date and amount; legitimate duplicates exist.

## Access design to implement later

Enable row-level security (RLS: rules restricting which rows a user can access) on
all private tables. Workspaces require `auth.uid() = user_id`; document and
transaction policies check ownership through their parent relationships for every
operation. Never accept a client-supplied `user_id` as proof of ownership.

Use a private Storage bucket and owner-scoped object paths (proposed:
`{user_id}/{workspace_id}/{document_id}/source.xlsx`). Storage policies must check
the owner too; an unguessable path alone is insufficient. Avoid names/account
numbers in paths. Issue short-lived authorized download links only when needed.

FastAPI still verifies token and workspace ownership. Prefer user-scoped database
access; if a future server uses a Supabase secret/service-role key that bypasses
RLS, explicit ownership checks become essential. Never put that key in the browser.
Supabase Auth owns passwords and login; no custom password table or login API.

No analysis/AI persistence tables are proposed yet. Decide retention, deletion,
failed-upload cleanup, access policies and the consistency strategy between
`parsed_json` and transaction rows before implementing storage. Never publish real
financial data in migrations, seed files, fixtures or logs.
