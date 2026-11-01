# Supabase foundation: first backend work package

This package adds the initial database, ownership policies, private source-file
bucket, and a protected identity endpoint. It is intentionally one reviewable
foundation change. Uploads, parsing, workspace routes and analysis remain separate
team tasks. No Git commits or pushes are part of setup.

## What exists

- `workspaces`, `documents`, `transactions`, with UUIDs and timestamps generated
  by default, exact `numeric` money, constraints and indexes.
- Row-level security on all three tables. Users can access only their own rows,
  including ownership checks through documents and transactions. Owner/parent
  changes must still belong to the caller. Anonymous clients have no table grants.
- One document per workspace, enforced by a unique constraint.
- Private `financial-documents` Storage bucket, accepting CSV/XLSX MIME types.
  Paths are `{user_id}/{workspace_id}/{document_id}/source.csv` or `source.xlsx`.
  Inserting an object requires matching owned workspace/document metadata first.
  An owner can read/delete their prefix even after metadata failure, permitting
  cleanup. There is no source-overwrite policy. File content validation and the
  application's maximum upload size are still upcoming work; MIME is not proof
  of file contents.
- `GET /api/me`, verified with Supabase Auth's `/auth/v1/user` HTTP endpoint.
  HTTPX is the only client dependency needed for this slice. No Supabase SDK,
  custom login endpoint, password table, secret key or service-role client is used.

The shared development project has the initial migration applied. The local file
version matches its hosted migration history; do not paste it into that project's
SQL Editor again. It can be applied once to a separate fresh project.

## Configure another teammate's backend

Keep the existing `backend/.env` and add these values from Supabase's Connect panel:

```dotenv
FINGENIE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
FINGENIE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_YOUR_KEY
```

`.env` is ignored. `.env.example` contains placeholders only. Keep database
passwords and elevated keys out of the repo and browser. The backend intentionally
accepts modern publishable keys; legacy anon keys are not supported by this slice.
The URL must be a project origin using HTTPS (local HTTP is allowed for localhost).
Restart FastAPI after changing its settings.

In the hosted dashboard, Authentication > URL Configuration should have Site URL
`http://localhost:5173` and redirect `http://localhost:5173/**`. The project owner
confirmed these are saved. Keep email/password authentication and email
confirmation enabled. Local CLI config contains equivalent development URLs.
Do not push local config over hosted settings to provision the database.

Run the backend normally from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

- `/api/health` stays public and works without Supabase configuration.
- `/api/me` with no token returns 401; a publishable key is not a user access token.
- After the frontend signs a user in with Supabase, send the session's access token
  as `Authorization: Bearer <access_token>`. Success returns only `{"id":"..."}`.
- Invalid/expired tokens give 401. Missing config or an unavailable Auth dependency
  gives a sanitized 503. No upstream responses, tokens or email addresses are exposed.

## Verification

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

The automated tests mock Supabase Auth; they need no real account or credentials.
They check token rejection, successful verified identity, separate user requests,
timeouts, malformed upstream responses and settings validation. The installed
Starlette currently emits a deprecation warning about its HTTPX TestClient adapter;
the tests pass. No unrelated framework upgrade is included in this package.

Run all of `supabase/tests/ownership.sql` as postgres in SQL Editor or through the
Supabase connector. It creates synthetic users and financial rows inside a
transaction, tests ownership/parent changes, anonymous access, Storage policies,
one-document constraints and exact-decimal validation, then rolls everything back.
Its Storage metadata inserts are test-only: real file operations must use Storage API.

These checks passed against the shared development database. A live backend request
with an invalid synthetic bearer token returned 401; health returned 200. Successful
real signup/login will be tested when the frontend auth UI or a developer session
exists. No real users or financial files were created by these tests.

The security advisor reported no findings. The performance advisor reports the
new transaction-pagination index as [unused](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index)
on the empty database; it is retained for the upcoming source-row transaction list.

## Local Supabase, optional

The committed CLI configuration was generated with Supabase CLI `2.122.0` and
reduced to the services needed here. It targets PostgreSQL 17, matching the hosted
project. A Docker-compatible container runtime is required to run the local stack;
that runtime is not installed in this workspace, so local database reset/replay
has not been tested. The migration and tests were verified on hosted Supabase.

Use this pinned CLI through `npx supabase@2.122.0`; discover each command's options
with `--help`. Future migrations must start with `supabase migration new <name>`.
Do not edit an already applied migration: add another. No CLI login credential,
remote link cache or database password is committed.

## Next work for the three backend members

1. API owner: reuse `require_user` with `Depends` in workspace routes. Implement
   list/detail/transaction pagination and consistent 404 behavior for unowned IDs.
2. Parser owner: agree supported banks, schemas and upload limits; add synthetic
   CSV/XLSX parsing fixtures. Balance-sheet parsing remains Sprint 2.
3. Supabase/persistence owner: add focused repositories and a transactional write
   for parsed JSON plus transaction rows. For uploads, reserve owned metadata,
   store the source file, then persist parsed results. Compensate storage/database
   failures explicitly; separate HTTP requests are not one database transaction.

Foreign keys currently restrict parent deletion. Before adding deletion endpoints,
agree retention and cleanup: deleting metadata alone never removes Storage bytes.
Frontend owns signup/login UI and session refresh. AI + Analysis owns calculations.
Review the new `/api/me` contract with Frontend before integrating it.
