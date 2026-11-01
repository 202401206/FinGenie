# Local database and persistence checks

Run from the repository root with Node.js/npm and the backend development Python
environment installed. The package lock pins the embedded PostgreSQL test engine.

```powershell
npm ci --prefix supabase/tests --ignore-scripts
npm test --prefix supabase/tests
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m ruff format --check app tests
```

Use your virtual environment's `python` command on macOS/Linux. No Supabase
credentials, Docker service, GitHub access or real financial files are required.
Installing the npm package needs registry access; the tests themselves run offline.

`database.mjs` builds a minimal test-only Auth/Storage schema and applies every
migration in filename order to an in-memory PostgreSQL engine (PGlite 0.3.14).
`run.mjs` executes the four SQL suites and checks that synthetic fixtures rolled
back, including cancellation rows. No test edits a hosted Supabase project.

`bridge.mjs` opens no network port. It accepts parameterized SQL over stdio from
the Python component test, uses the authenticated role and synthetic JWT subject
for user operations, and closes with the test process. Its administrative fixture
setup and direct Storage metadata writes exist only in the test harness. Production
file operations must use the Storage API. JSON payloads travel into PostgreSQL as
raw text parameters so JavaScript never rounds their monetary numbers.

The eight component tests in
`backend/tests/integration/test_persistence_recovery.py` use actual authentication
verification code, repositories, recovery and Storage helpers. The HTTP adapter
simulates Auth and Storage responses/bytes while running real SQL and RLS for the
database operations. It is intentionally limited to the requests under test,
not a replacement PostgREST/Storage server. These tests skip with a visible reason
if Node or the npm dependency is missing; install them before claiming integration
passed. With dependencies installed, the current suite has 218 passing tests.

For a full Supabase deployment, separately review migrations, run the SQL suites
against a dedicated disposable/local test database as postgres, and test actual
file upload/deletion and two-user HTTP access. The SQL files create synthetic Auth
and Storage metadata in transactions. Never replace a production Auth/Storage
schema with `database.mjs`, and do not present this embedded test as a hosted or
browser test. Independent-session lock contention is not exercised by this runner.
