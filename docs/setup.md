# Local setup, one step at a time

Run these commands yourself. Nothing here was installed or configured by the
scaffold. Use two terminals: one for FastAPI, one for Vite. Start in the `FinGenie/`
directory containing this README, `frontend/` and `backend/`.

## 1. Required software

Install Git, Node.js with npm, and Python 3.11+ yourself. Python 3.11 is a simple
baseline for this project; use a dependency-compatible newer version if preferred.
Use Node.js 22.12+ (an actively supported LTS release is preferable). The selected
Vite baseline requires a modern Node version; see [Vite's guide](https://vite.dev/guide/).
Avoid switching Node/Python versions between teammates without agreeing first.

Verify in a fresh terminal:

```sh
git --version
node --version
npm --version
```

Windows PowerShell:

```powershell
py -3.11 --version
```

macOS/Linux:

```sh
python3 --version
```

These print versions; they do not install software. If a command is not found,
check installation/PATH and reopen the terminal. If Python 3.11 is not installed
but another compatible 3.11+ interpreter is, select that interpreter explicitly.

## 2. Create an isolated Python environment

An environment keeps this project's Python packages separate from other projects.
Create it once; activate it each time you open a new backend terminal.

Windows PowerShell, from `FinGenie/`:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -m pip --version
```

macOS/Linux, from `FinGenie/`:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
python --version
python -m pip --version
```

`-m venv` creates `.venv`; activation makes `python` use it. Verify pip's printed
path contains `backend/.venv` before installing. `deactivate` leaves it later.

## 3. Install backend dependencies

From `backend/`, with the environment active, on either platform:

```sh
python -m pip install -r requirements-dev.txt
```

This reads development dependencies and includes `requirements.txt` automatically.
For runtime dependencies only, use `python -m pip install -r requirements.txt`.
You do not need both commands for normal development.

| Package | Why it is listed |
| --- | --- |
| FastAPI | Defines the HTTP application and routes |
| Uvicorn | Runs the Python web server |
| Pydantic | Checks and describes structured data |
| pydantic-settings | Reads optional environment settings and `.env` files |
| Pandas | Planned CSV/XLSX table processing; unused in this scaffold |
| OpenPyXL | Planned XLSX reading support; unused in this scaffold |
| pytest | Runs backend tests |
| HTTPX | Supports FastAPI's in-process TestClient |
| Ruff | Python linting and formatting; no Black needed |

## 4. Install frontend dependencies

In a second terminal, from `FinGenie/`:

```sh
cd frontend
npm install
```

This installs packages from `package.json` and generates `package-lock.json`.
React/React DOM render the UI. Vite and its React plugin serve/build JSX. ESLint,
its React Hooks/Refresh plugins, `@eslint/js` and `globals` check JavaScript.
Prettier formats frontend code. No Axios or component library is needed.
The ESLint config uses the [flat configuration format](https://eslint.org/docs/latest/use/configure/configuration-files).

No Supabase, LangChain/LangGraph, Ollama, Groq, RapidFuzz, multipart or rate-limiter
packages are needed to start this foundation. Add them with affected-team review
when implementing the corresponding feature, then document their configuration.
No service accounts or keys are required for health or the title page. `GET /api/me`
uses HTTPX to verify tokens; configure it using [Supabase setup](supabase-setup.md).

## 5. Create local environment files

In each terminal, already in its respective `backend/` or `frontend/` directory:

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```sh
cp .env.example .env
```

Do this once, before customizing `.env`; copying again replaces your local values.
The defaults work locally. Backend settings use the `FINGENIE_` prefix and load
`backend/.env` when launched from `backend/`. `FINGENIE_CORS_ORIGINS` is a JSON array
of exact browser origins. See [FastAPI settings](https://fastapi.tiangolo.com/advanced/settings/).

Frontend uses `VITE_API_BASE_URL=http://localhost:8000/api`. Every `VITE_` value
is public browser code. Leave frontend Supabase placeholders blank until auth UI integration.
Only a public/publishable Supabase key may go there; secret/service-role
keys and LLM keys stay server-side. Never commit `.env`. Restart Vite after editing
its environment file. Backend Supabase Auth configuration is documented separately;
there is no frontend Supabase client or AI config code yet.

## 6. Run the backend

In the active backend environment, from `backend/`:

```sh
python -m uvicorn app.main:app --reload --port 8000
```

`app.main:app` identifies the `app` object in `app/main.py`. `--reload` restarts
after code edits and is for local development. Keep this terminal running.

Open <http://localhost:8000/docs> for interactive FastAPI documentation.
<http://localhost:8000/openapi.json> describes implemented routes only; the future
API plan lives in `contracts/api/README.md`.

Verify <http://localhost:8000/api/health> in a browser or another terminal:

Windows PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

macOS/Linux:

```sh
curl http://localhost:8000/api/health
```

Expected JSON: `{"status":"ok","service":"fingenie-api"}`. This checks the app,
not Supabase, authentication or AI. `/api/me` requires a valid token. Other planned
endpoints return 404 for now.

## 7. Run the frontend

In the frontend terminal, from `frontend/`:

```sh
npm run dev
```

Open <http://localhost:5173>. You should see the FinGenie title. No feature UI or
automatic API call is implemented. Vite uses a fixed port so CORS remains predictable.
Stop either server with Ctrl+C.

## 8. Run checks after installing

From `backend/`, with the environment active:

```sh
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

pytest checks health, auth status/error handling, user isolation and configuration
using an in-process client and mocked Auth calls, without live credentials or a
running server. Ruff checks common errors/import ordering, then formatting.
To format Python deliberately, use `python -m ruff format .`.

From `frontend/`:

```sh
npm run lint
npm run format:check
npm run build
```

Lint checks JS/React rules; the format check does not change files. Build checks
that Vite can bundle the app. Use `npm run format` to format frontend files
deliberately, and `npm run preview` after a build to inspect the generated bundle.
The root Prettier settings are discovered from `frontend/`; Ruff alone formats Python.

## 9. Dependency versions and lockfiles

Manifests contain bounded baseline ranges, not an exact tested dependency snapshot.
No lockfile was fabricated. After the first successful `npm install`, review and
commit `frontend/package-lock.json` so teammates can use `npm ci` for the same
resolved dependency tree. `npm ci` requires an existing lockfile matching the manifest.

After a successful backend setup, optionally capture an exact snapshot from the
clean virtual environment:

```sh
python -m pip freeze > requirements-lock.txt
```

Review it with the team before committing. A later `python -m pip install -r
requirements-lock.txt` reproduces its versions on a compatible Python/platform.
`pip freeze` records the current environment; it is not a cross-platform solver.
Keep the two curated requirements files as the dependency intent. Add new direct
dependencies there rather than manually editing an existing lock artifact.

## 10. Common mistakes

| Symptom | What to check |
| --- | --- |
| PowerShell blocks activation | Use the environment's interpreter directly: `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`, then `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000`. No execution-policy change is required. |
| `No module named app` | Launch Uvicorn from `backend/`, not the repo root. |
| `No module named fastapi/pytest` | Verify `python -m pip --version` points to `.venv` and install the correct requirements file. |
| `npm` or `node` missing/too old | Install a suitable Node version, reopen the terminal and check versions. |
| `npm` script blocked in PowerShell | Try `npm.cmd install` or `npm.cmd run dev` with the same arguments. |
| Vite reports port 5173 in use | Stop the other local process using it; do not silently change the port without updating backend CORS. |
| Backend port 8000 in use | Stop the old server or choose another port and update `VITE_API_BASE_URL`, then restart Vite. |
| Browser reports CORS error | Match scheme, host and port exactly in `FINGENIE_CORS_ORIGINS`; restart FastAPI. CORS is not auth. |
| `.env` changes ignored | Use the right directory/prefix and restart the relevant server. Check the file is not named `.env.txt`. |
| Planned endpoint returns 404 | Only `/api/health` and `/api/me` exist. Consult the sprint plan. |
| XLSX import fails in future parser work | Ensure OpenPyXL is installed in the active environment; parsing is not implemented now. |
| Linux Python cannot create a venv | Install your OS's Python venv support manually, then repeat step 2. |

Do not paste secrets or financial document contents into bug reports or logs.
