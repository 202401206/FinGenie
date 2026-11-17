# Supabase schema

The initial migration implements the three tables below with ownership/RLS and a
private `financial-documents` Storage bucket. Their fields come from the
brainstorming PDF (page 4). The migration adds the implementation constraints and
indexes described below. See [setup and verification](supabase-setup.md).

| Table | Planned fields |
| --- | --- |
| `workspaces` | `id uuid PK`, `user_id uuid FK auth.users(id)`, `user_type text`, `document_type text`, `name text`, `created_at timestamptz` |
| `documents` | `id uuid PK`, `workspace_id uuid FK workspaces(id)`, `file_path text`, `original_filename text`, `currency text`, `period_start date nullable`, `period_end date nullable`, `status text`, `parsed_json jsonb nullable`, `created_at timestamptz` |
| `transactions` | `id uuid PK`, `document_id uuid FK documents(id)`, `date date`, `description text`, `debit numeric`, `credit numeric`, `balance numeric`, `source_row integer` |

Relationships: user -> many workspaces -> documents -> transactions. V1 accepts one
document per workspace, enforced by `documents.workspace_id` being unique. Balance sheets stay
in `documents.parsed_json`; their reporting date and scale are preserved there.
Document status is `uploaded`, `parsed` or `failed`. Do not invent additional states
until an actual workflow requires them.

Implemented constraints: allowed user/document enum values, personal users cannot
select balance sheets, nonnegative debit/credit, positive source rows. Generate IDs
and timestamps by default. Indexes cover `workspaces(user_id, created_at, id)`,
unique `documents(workspace_id)`, `transactions(document_id, date)` and
`transactions(document_id, source_row, id)`. Money must be finite; balances may be
negative. Parsed documents require a JSON object. Known periods must be ordered.
Use exact PostgreSQL `numeric` for money, not floating point. Nullable metadata
means unknown, not zero or an empty date. Do not deduplicate transactions solely on
date and amount; legitimate duplicates exist.

## Implemented access rules

Row-level security (RLS: rules restricting which rows a user can access) is enabled on
all private tables. Workspaces require `auth.uid() = user_id`; document and
transaction policies check ownership through their parent relationships for every
operation. Never accept a client-supplied `user_id` as proof of ownership.

The private bucket uses owner-scoped object paths:
`{user_id}/{workspace_id}/{document_id}/source.csv` or `source.xlsx`. Document
constraints enforce the workspace/document path segments; insert/update policies
enforce the owner prefix. Storage inserts require exact matching owned metadata.
Reads and deletes require the caller's owner prefix, including orphan cleanup.
No UPDATE policy permits source overwrite. Avoid names/account numbers in paths.
Add short-lived authorized download links only when a future route needs them.

FastAPI verifies tokens for `/api/me`; future workspace routes must verify ownership.
Use user-scoped database
access; if a future server uses a Supabase secret/service-role key that bypasses
RLS, explicit ownership checks become essential. Never put that key in the browser.
Supabase Auth owns passwords and login; no custom password table or login API.

No analysis/AI persistence tables are proposed yet. Foreign keys restrict parent
deletion; agree retention and file cleanup before adding deletion endpoints.
The persistence branch adds metadata reservation, private source helpers, atomic
parsed-data save and [controlled recovery](../backend/app/services/upload-recovery.md).
The follow-up recovery migration adds `upload_cancellations` with owner, workspace
and document UUIDs plus a timestamp. Its `(user_id, workspace_id)` primary key
records cancelled attempts after their metadata is removed, blocking late writes.
Owner RLS allows select/insert only; ordinary clients cannot update/delete these
records. Retention and account deletion need an explicit reviewed policy.
Storage INSERT additionally requires the matching pending document and no
cancellation. Reads/deletes retain their owner-prefix rules. The API/parser
owners still need to connect their public workflows to these helpers.
Never publish real financial data in migrations, seed files, fixtures or logs.

## Sprint 2 balance snapshot finalization

The local migration `20261116201152_finalize_balance_sheet.sql` adds
`finalize_balance_sheet(workspace_id, document_id, parsed_json)`. It adds no tables
or columns. Business balance data remains in `documents.parsed_json`, with known
currency in metadata and bank period columns null. Reporting date, unit scale,
prior periods and traceability stay in JSON; reported amounts are not rescaled.
The operation returns a zero transaction count and inserts no bank transactions.

The function runs with caller privileges/RLS, checks the owned pending document
and canonical registered source, respects cancellation, and uses the existing
upload lock order. It saves metadata/JSON/status atomically and rejects repeats.
This file has been tested locally, not deployed by this work. Balance parser,
public dispatch and recovery integration are separate milestones; keep public
balance uploads disabled until those pieces are reviewed together.

## Settings and financial-data deletion

The local settings migration adds `user_preferences` (owner UUID, selected currency
and theme), `financial_data_state` (owner and monotonically increasing upload
generation), `data_deletion_jobs` (owner-scoped operation UUID/status/timestamps)
and `data_deletion_sources` (owned source path/removal progress).

Owner RLS and narrow grants protect these tables. Invoker RPCs perform atomic
partial preference updates and resumable deletion. Evidence triggers prevent
generation rollback, false source-removal acknowledgements and unverified job
completion; journal insertion initializes the snapshot/generation even through a
direct owner table insert. Source paths are purged after successful completion.
No Auth tokens or parsed financial JSON are stored in these deletion tables.

Financial deletion keeps Auth identities and preferences. Existing cancellation
UUIDs and generation counters remain to reject late upload/finalization writes.
The account lock precedes existing workspace locks; uploads are blocked while a
deletion is pending. No new financial rows or currency conversion are introduced.
See [settings handoff](settings-api-handoff.md). Hosted deployment is still a
separate reviewed step; embedded tests do not replace actual Storage verification.
