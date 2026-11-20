# Sprint 2 persistence verification and remaining integration gates

P5 adds repeatable local verification, a catalog security audit and explicit
cross-branch compatibility tests. It does not implement the API team's A2-A4
routes, merge branches or deploy hosted migrations. P4 is a prerequisite.

Verified on 20 November 2026 in the persistence working tree: 1,094 backend tests
passed, all eight behavioral SQL suites and the catalog audit passed, Ruff
lint/format and pip check passed. One existing Starlette TestClient deprecation
warning remains. The API prerequisite gate remains NOT READY; hosted checks are
not included in these results.

## Local verification

Install the existing backend development dependencies and Node/npm, then run
`npm ci --prefix supabase/tests` from the repository root. With the backend Python
environment active, run from backend:

```bash
python scripts/verify_sprint2.py --local-only
```

This runs the full tests/ suite, Ruff lint/format, pip check, all eight behavioral
SQL suites and the separate catalog security audit. Missing SQL dependencies fail
the command instead of treating skipped database tests as complete verification.
It also prints API prerequisites but permits a local-only success while those are
missing. Local success is not Sprint 2 release approval.

For a strict local/API-prerequisite check:

```bash
python scripts/verify_sprint2.py
```

Exit 0 means the requested scope passed, exit 1 means a local check failed, and
exit 2 means API prerequisites remain incomplete. Windows shells may display a
generic failure indicator; the Python process uses those codes. To inspect just
the prerequisites, use --readiness-only. Optional --report PATH writes a JSON
record of check results without tokens, financial JSON or private source paths.
Use an ignored local-only path for personal evidence.

The prerequisite check inspects mounted routes, verified-owner dependencies, the
balance parser entry point and the advertised upload type. An empty parser
package does not qualify. Presence checks are not substitutes for behavioral
API tests, hosted Auth/Storage checks or another team member's review.

## What is tested by the lead's local suite

The new component tests cover journal/save/read feeding the existing pure bank
and balance analysis modules and deterministic offline summaries, with original
workspace/document IDs and exact Decimal extras preserved. They also combine
lost-save recovery with financial-data deletion and foreign-user denial.

The balance inputs in that normal suite are validated contract fixtures. This
does not claim the real balance byte parser or public balance upload route is
already installed on the persistence branch. Summary tests pass owned reader
output directly to the existing pure function with an explicitly unconfigured
provider; they do not certify the production summary route's ownership behavior.

The catalog audit checks all tables/functions introduced into the disposable
public schema by this repository's migrations. It checks RLS, operation policies,
anonymous table and column grants, excessive authenticated grants, invoker/empty
search-path functions, immutable journal columns, cancellation evidence and
private/non-overwritable source policies. It is intentionally conservative about
new public views and objects that need an explicit review.

Regression tests deliberately disable protections in a disposable database,
confirm that the shared audit rejects each mutation, restore the protection and
confirm the audit passes again. No hosted database is weakened by these tests.
This catalog audit complements the existing owner/foreign behavioral SQL suites;
policy existence alone does not prove an ownership predicate is correct.

Run the audit alone from the repository root:

```bash
npm run test:security --prefix supabase/tests
```

The standalone SQL file is supabase/tests/security_audit.sql. It targets the
disposable schema built from this repository. A hosted project's extensions and
unrelated objects require a scoped review, not an unqualified claim based on this
fresh-schema audit. Hosted Supabase advisors remain a separate check.

## Explicit cross-branch verification

Once Dhaval's real parser and Anshuman's A1 analysis route are integrated into the
same checkout as the persistence/journal migrations, run from backend:

```bash
python -m pytest verification/test_balance_parser_persistence.py -q
python -m pytest verification/test_owned_analysis_api.py -q
```

These files live outside the default tests/ path because they deliberately
require teammates' real dependencies. Missing dependencies fail; no fake parser,
test-only route or silent skip is substituted.

The parser suite exercises Layout A and B as CSV and XLSX through the actual
parser, exact input bytes into Storage, journal, atomic save, owned reader,
analysis and repeat recovery. It checks zero balance transactions, null bank
period columns, original UUIDs, prior-period preservation and foreign denial.

The API suite uses the actual mounted A1 route against real SQL/RLS with synthetic
Auth/Storage. It checks complete current metrics and owner/foreign/missing IDs.
It does not certify A2 public uploads, A3 owned summaries or A4 attempt routes.
Those require their own completed implementation and combined API tests.

## Compatibility issue found on 20 November 2026

An isolated verification copy combined parser/integration commit cab84cc,
Anshuman's A1 commit 18a6cb8 and the lead's current persistence/journal changes.
The four real parser/layout-format persistence checks passed. The A1 Layout B
check failed: valid comparative input was reported as insufficient_data because
the policy treats every unmapped entry as an incomplete financial classification.
Prior-period values are intentionally stored in unmapped.

Recommended A1 correction: allow the documented nonblocking reasons
prior_period_value, reported_subtotal, unrecognized_note and repeated_reported_value.
Continue withholding current metrics for unknown/missing reason codes,
unrecognized_financial_item, ambiguous_section, missing classifications/amounts
or missing currency/scale. Do not simply ignore all unmapped entries.

A candidate allowlist correction was tested only in the ignored verification
copy: the six explicit compatibility tests plus A1's existing analysis tests
passed, 31 total. This correction has not been applied to Anshuman's branch or
merged by this work. The API owner needs to implement/review it and rerun the
tests after integration.

## Readiness and hosted verification still required

The reviewed persistence checkout does not yet include the real balance parser,
A1 analysis route, A2 balance dispatch, A3 owned summary lookup or A4 public
attempt endpoints. The existing summary route still uses development fixture
lookup; its existence must not be presented as owned saved-document integration.

The connected FinGenie project was INACTIVE when checked on 20 November 2026.
No hosted migration, Auth/Storage operation, advisor run or independent-session
contention test was performed. Local evidence cannot certify those checks.

Before Sprint 2 is called complete:

1. Commit/review the lead's P4 and P5 changes separately, then integrate the
   reviewed dependency slices into feature/backend-sprint-2. Resolve overlaps
   without replacing Anshuman's upload changes wholesale.
2. Integrate Dhaval's parser and Anshuman's A1 correction, A2, A3 and A4. Keep
   original upload IDs/generation, receipt fields and exact stored values.
3. Run the local command, strict prerequisite check and both explicit suites.
   Exercise the completed bank/balance upload/read/analysis/summary/attempt routes
   together, including unknown metadata and unreliable inputs.
4. Have the project owner resume the intended development Supabase project and
   inspect its actual migration history. Review and deploy only missing migrations
   in order; do not rerun foundation SQL blindly. This change authorizes no hosted
   schema deployment or project restoration.
5. Use two disposable development users and synthetic CSV/XLSX statements. Check
   actual source upload/removal, private access, foreign/missing 404 behavior and
   source references. Do not use real financial data or privileged-key shortcuts.
6. Demonstrate restart/re-authentication recovery using the same persisted attempt
   IDs. Check lost responses, pending cleanup and preservation of completed or
   conflicting sources without replaying POST uploads under new IDs.
7. Test independent database-session lock contention and run hosted advisors.
   Embedded PostgreSQL/request interleaving is a different kind of evidence.
8. Obtain Frontend and AI + Analysis contract review. Live AI-provider calls need
   the owner's explicit authorization and configured development credentials;
   local verification does not make those calls.

Record project, migration versions, safe IDs/statuses, commands, results and
remaining limitations in ignored personal evidence. Never record credentials or
full financial payloads there. Keep the final integration PR into main open until
the actual acceptance checks pass.
