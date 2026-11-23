# Sprint 2 backend verification

Updated 24 November 2026 on `feature/backend-sprint-2-hardening`.
The parser, owned analysis/summary routes, balance upload dispatch and public
upload-attempt routes are integrated in this checkout. The original P5 notes
from 20 November described an earlier persistence-only checkout; their missing
API and inactive-project gates have now been checked against the integrated code.

## Repeat the local checks

Install `backend/requirements-dev.txt` using Python 3.11 and install Node/npm.
From the repository root, install the pinned disposable SQL test engine:

```bash
npm ci --prefix supabase/tests --ignore-scripts
```

With the backend Python environment active, run from `backend/`:

```bash
python scripts/verify_sprint2.py
```

The default command runs:

- The backend suite with strict pytest markers and a JUnit report.
- Ruff lint/format, `pip check`, eight behavioral SQL suites and the catalog audit.
- Both explicit parser/persistence and owned-analysis acceptance modules in
  `backend/verification/`, which are outside pytest's default `tests/` path.
- A report check that rejects empty, failed, skipped or missing test reports.
- Seven API prerequisite checks covering mounted owned routes, the real balance
  parser and the advertised balance upload type.

Missing parser/route dependencies fail acceptance; no fixture implementation or
silent skip substitutes for them. Child checks receive empty Supabase and Groq
settings even if the developer has configured local credentials. These checks
use disposable PostgreSQL and synthetic Auth/Storage or mocked/offline providers.
They do not contact the hosted project or a live AI provider.

`--local-only` runs the normal suite and SQL checks, omits the two explicit
cross-branch acceptance modules and permits missing API prerequisites. Use the
default command for final integration verification. `--readiness-only` inspects
prerequisites without running tests; route presence alone does not prove behavior.

Exit codes: `0` means the requested scope passed, `1` means a local check failed,
and `2` means required API prerequisites are incomplete. `--report PATH` writes
JSON without credentials or financial payloads; use an ignored personal path.
The report always leaves hosted checks as `not_run` and release approval false,
because this command cannot certify external verification or team signoff.

## Verified local result

On 24 November, Python 3.11.16 and Node 24.20.0 passed **1,343 backend tests and
six explicit acceptance tests, with zero skips**. All eight SQL suites, the
catalog security audit, Ruff lint/format, dependency consistency and all seven
API prerequisites passed. An existing Starlette TestClient deprecation warning
remains; it did not skip or fail tests.

The explicit checks cover Layout A/B CSV/XLSX through the real balance parser,
source-byte preservation, journal, atomic save, exact Decimal read, analysis and
repeat recovery. Balance receipts have zero transactions and null bank-period
columns. The owned-analysis route is exercised with owner, missing and foreign
workspace IDs. Comparative prior-period entries no longer incorrectly block
otherwise complete current-period metrics in this integrated checkout.

The catalog audit checks ownership policies, grants, invoker functions, safe
search paths, journal guards and private source policies. Regression tests weaken
and restore protections only in a disposable database. Run it separately with
`npm run test:security --prefix supabase/tests`. Hosted extensions and unrelated
objects require a scoped review rather than assuming this fresh-schema audit
certifies the whole hosted project.

## Hosted development verification

The existing FinGenie development project was resumed, and the owner explicitly
approved the seven missing repository migrations and their migration-history
alignment. The existing foundation was neither reset nor rerun. All eight
canonical versions now match the [migration inventory](../supabase/migrations/README.md).

Two newly created, confirmed, initially empty test accounts were used with
synthetic documents. Ordinary verified user tokens and the publishable key were
used for application requests; there was no service-role shortcut around RLS.
The actual backend ran in a separate Uvicorn process against hosted Auth,
PostgreSQL and private Storage. Hosted checks passed for:

- Bank CSV/XLSX and balance Layout A/B CSV/XLSX upload, owned analysis, offline
  summaries, source references and exact downloaded source bytes.
- Foreign/missing workspace and attempt denial, including recovery; source files
  remained private. Balance receipts retained `transaction_count=0`.
- Lost finalization responses for bank and balance uploads, a backend process
  restart, recovery using the original IDs and repeated recovery. Completed data
  and original source bytes were preserved.
- Unfinished uploads and simulated Storage deletion failures for both types.
  Failed cleanup stayed pending and later recovery cleaned it safely.
- A deliberately conflicting owned snapshot remaining `needs_review` across
  repeat recovery, with its source preserved. It was removed only afterward by
  explicit test-user financial-data deletion, not forced recovery cleanup.
- Missing currency and unreliable balances withholding summaries; stale deletion
  keys refusing to remove newer data; idempotent current deletion requests.
- Financial-data deletion retaining Auth/preferences and preserving the other
  user's files, followed by fresh authentication and confirmed test cleanup.

Response loss and cleanup failures were injected at the HTTP transport boundary;
Auth, SQL and Storage operations were real. This verifies recovery after those
controlled failures, not the reliability of every possible network outage.

Independent-session lock contention was also observed. A deliberately held
owner lock made that owner's authenticated RPC time out (PostgreSQL `57014`,
HTTP 500), while another user's RPC returned 204. After release both returned
204 and the holder session was gone. This demonstrates blocking, owner isolation
and successful retry; it does not claim a blocked call succeeds before timeout.
The raw timeout result is retained alongside its diagnosis in private evidence.

Final test-scoped checks found zero workspaces, documents, journal attempts and
source files for the two accounts. Auth, preferences and minimal deletion/
cancellation evidence remain by design. No real financial data was used.

The hosted catalog review found RLS enabled on all nine application tables, no
anonymous table access, no authenticated TRUNCATE grants, 29 application functions
using invoker privileges with safe empty search paths, and a private source bucket.
The security advisor still reports **Leaked Password Protection Disabled**.
See [Supabase's remediation](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
This Auth setting has not been changed by backend verification.

## CI and remaining scope

[Backend and SQL CI passed for `fc1df9e`](https://github.com/202401206/FinGenie/actions/runs/45240040473)
on GitHub. That run covers H2, before these final verifier changes; the next
commit must pass its own push/PR workflow before merging.

This completes the lead's H3 verification work in this checkout. It does not
complete Anshuman's A6 calculations, A7 dashboard endpoint or A8 integration/
handoff, certify the frontend/browser experience, or supply team contract review.
No live Groq calls were made; summaries were checked in deterministic offline
mode. Rate limiting remains per-process memory and requires one worker for the
documented limits; distributed deployment is outside that guarantee.

Deploy the reviewed application and migrations together. Follow the Settings
generation/deletion contract and recover pending attempts by their existing IDs
instead of blindly repeating uploads. Keep credentials, test-account passwords,
viva notes and detailed hosted evidence in ignored `local-only/`. The user owns
Git commits, pushes, PRs and merges.
