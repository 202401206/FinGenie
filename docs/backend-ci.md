# Backend and SQL verification in GitHub Actions

`.github/workflows/backend.yml` adds the **Backend and SQL Verification** job on
pushes and pull requests, including feature/integration branches. It also supports
manual dispatch once the workflow is available in the default branch. It is a
separate workflow and does not replace the frontend checks on main.

## What the job checks

The job uses Ubuntu 24.04, Python 3.11 and Node 24. It installs backend development
requirements and the SQL harness from its npm lockfile, then runs:

1. Python dependency consistency, Ruff lint and formatting across `backend/`.
2. All eight local SQL suites, applying the repository migrations to disposable
   embedded PostgreSQL and checking that synthetic fixtures roll back.
3. The local SQL ownership/privilege catalog audit.
4. The complete backend pytest suite, including API and SQL component integration.
5. Both explicit parser/persistence and owned-analysis acceptance suites. These
   live outside pytest's default `tests/` path and must be invoked explicitly.
6. A JUnit report check that rejects missing/empty reports, skipped cases, errors
   or failures. Missing Node/PGlite therefore cannot silently produce green CI.
7. The strict mounted-API prerequisite check for owned analysis/summary, public
   upload-attempt list/detail/recovery, the parser and balance upload declaration.

No `--local-only` bypass or `continue-on-error` is used. A backend test, SQL audit
or required readiness failure fails the job. Passing these checks is local CI
evidence, not hosted Supabase or browser acceptance.

## Credentials and reports

GitHub Actions has read-only repository contents permission. Checkout does not
persist its Git credentials. Actions are pinned to reviewed release commit hashes;
update those hashes deliberately when upgrading. Dependency downloads use pip/npm
caches; npm lifecycle scripts are disabled for the SQL harness installation.

No project credentials or GitHub secrets are needed. The workflow explicitly
leaves Supabase settings and the AI-provider key blank. Tests use synthetic Auth,
Storage and financial fixtures; providers are mocked or offline. Nothing applies
migrations to a hosted database, restores a Supabase project or calls a live LLM.

Pytest writes `test-results/backend.xml` and `test-results/sprint-2-acceptance.xml`.
Reports are available as the `backend-test-results` artifact for seven days,
including reports produced before a later step failed. A setup failure may occur
before any report exists; that remains a failed job, not a passing empty artifact.
Never introduce real financial fixtures or credentials into these reports.

## Run the same checks locally

Use the project's development virtual environment. From the repository root:

```powershell
npm ci --prefix supabase/tests --ignore-scripts
npm test --prefix supabase/tests
npm run test:security --prefix supabase/tests
```

Then from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q --strict-markers --junitxml=../test-results/backend.xml
.\.venv\Scripts\python.exe -m pytest -q --strict-markers verification/test_balance_parser_persistence.py verification/test_owned_analysis_api.py --junitxml=../test-results/sprint-2-acceptance.xml
.\.venv\Scripts\python.exe scripts/check_test_results.py ../test-results/backend.xml ../test-results/sprint-2-acceptance.xml
.\.venv\Scripts\python.exe scripts/verify_sprint2.py --readiness-only
```

Use an unconfigured AI key or explicitly mocked providers when running tests. Do
not use your hosted Supabase project as the SQL test database. XML reports are
generated local output and are ignored by Git.

## Review failures through GitHub

Open the PR's Checks tab and select **Backend and SQL Verification**. Inspect the
first failed step and its error before retrying. A readiness/Layout B failure on
an old branch can indicate missing #16 integration; bring in the real dependency
instead of disabling the gate or replacing it with synthetic production data.

After the team observes a successful hosted Actions run, the repository owner can
select this job as a required status check in the appropriate GitHub ruleset.
Adding this file does not change branch protection automatically. Hosted Auth,
Storage, independent database-session contention and frontend acceptance remain
the final Sprint 2 verification milestone.
