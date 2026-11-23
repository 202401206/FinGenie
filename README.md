# FinGenie

A semester team project for understanding financial documents through dashboards
and an AI assistant.

The integrated Sprint 2 backend supports authenticated bank/balance CSV/XLSX
uploads, private sources, atomic parsed persistence, owned reads/analysis/summaries,
durable manual upload recovery and Settings preferences/financial-data deletion.
Personal users upload bank statements; business users may also upload balance
sheets. Dashboard calculations/endpoints and frontend integration have separate
team milestones. A working persistence flow does not mean the whole app is finished.

See [database access](backend/app/db/README.md),
[source uploads](backend/app/services/source-uploads.md),
[parsed persistence](backend/app/db/parsed-documents.md), and
[Sprint 2 verification](docs/sprint-2-verification.md) for tested behavior and limits.

One monorepo (a repository containing both frontend and backend), one modular
FastAPI server, exactly three development teams. Supabase will provide Auth,
PostgreSQL and private file storage. See [Supabase setup](docs/supabase-setup.md)
and the [migration inventory](supabase/migrations/README.md) for configuration
and the current development deployment.

## Start here

Follow [setup](docs/setup.md) for complete Windows and macOS/Linux instructions.
From this directory, after installing Git, Node.js and Python yourself:

```powershell
# Windows PowerShell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

In another terminal:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open <http://localhost:5173>, <http://localhost:8000/docs>, and
<http://localhost:8000/api/health>. Configure the local environment files using
the setup guide; protected endpoints require a valid Supabase user session.
Run the backend checks in [Sprint 2 verification](docs/sprint-2-verification.md).

## Find your work

| Directory | Purpose | Owner |
| --- | --- | --- |
| `frontend/` | React UI, API client, local mocks | Frontend |
| `backend/app/api`, `core`, `schemas`, `services`, `parsers`, `db` | API and integration | Backend |
| `backend/app/analysis`, `ai` | Pure calculations and AI modules inside the same server | AI + Analysis |
| `contracts/` | Proposed shared API and JSON agreements | Affected teams together |
| `supabase/migrations/` | Future SQL changes | Backend |

See [architecture](docs/architecture.md), [ownership](docs/team-ownership.md),
[planned database](docs/database-schema.md), [contracts](contracts/README.md),
and [contributing](CONTRIBUTING.md).

The requirements were read from the supplied *FinGenie Brainstorming Session*
(seven pages). [Decision notes](docs/decisions/0001-foundation.md) distinguish
those requirements from the user's refinements and proposed conventions.
The PDF and real financial documents are deliberately not copied into the repo.

## Before committing

- Install dependencies manually and run the checks in `docs/setup.md`.
- Review shared API/schema changes with affected teams; examples use synthetic data.
- Check `git status` and staged changes for secrets, `.env`, raw financial data,
  virtual environments and `node_modules`.
- Keep personal planning, viva notes and hosted verification evidence in ignored `local-only/`.
- Follow `CONTRIBUTING.md` and require the relevant CI checks before merging.
