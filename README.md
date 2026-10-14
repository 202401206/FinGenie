# FinGenie

A semester team project for understanding financial documents through dashboards
and an AI assistant. This repository is the foundation, not the application.

**Implemented:** a React title page and `GET /api/health`.
**Planned:** CSV/XLSX upload, Python parsing, deterministic financial calculations,
dashboards, summaries, chat and bank-statement projections. Personal users may
upload bank statements; business users may also upload balance sheets.

One monorepo (a repository containing both frontend and backend), one modular
FastAPI server, exactly three development teams. Supabase will provide Auth,
PostgreSQL and private file storage. No external service is connected yet.

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
<http://localhost:8000/api/health>. The title page does not fetch the API yet.
No dependency installation or runtime verification was performed when generating
this scaffold. Run the checks in the setup guide after your manual installation.

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

## Before the initial commit

- Install dependencies manually and run the checks in `docs/setup.md`.
- Review contracts with affected teams; examples are synthetic, not API responses.
- Check `git status` and staged changes for secrets, `.env`, raw financial data,
  virtual environments and `node_modules`.
- Commit the generated `frontend/package-lock.json` after reviewing it.
- Decide the first supported banks, sample-file steward and contract reviewers.
- Follow `CONTRIBUTING.md` to initialize Git and enable basic PR protection yourself.
