# Sprint 2 dashboard API handoff

## Request and examples

The implemented route is `GET /api/workspaces/{workspace_id}/dashboard`.
Use the workspace ID returned by upload. Send the signed-in user's access token
in the Authorization header. The request has no body.

```javascript
const response = await fetch(
  `${apiBase}/api/workspaces/${workspaceId}/dashboard`,
  { headers: { Authorization: `Bearer ${accessToken}` } },
);
const body = await response.json();
```

Complete synthetic 200 responses are available for a
[bank statement](../contracts/examples/bank-dashboard.json) and a
[balance sheet](../contracts/examples/balance-sheet-dashboard.json).
They are generated from the supported Layout A CSV fixtures. Integration tests
compare them with actual upload/read responses after substituting the example
workspace and document IDs. OpenAPI is available at `/openapi.json`.

The dashboard covers the whole saved document. The
`/api/workspaces/{id}/transactions` endpoint still returns a paginated table.

## Response fields

| Field | Meaning |
| --- | --- |
| workspace_id, document_id | IDs of the owned saved workspace and document |
| document_type | bank_statement or balance_sheet |
| metadata | Nullable company, currency, period_start, period_end, reporting_date and unit_scale |
| analysis | Existing analysis envelope with dashboard metrics appended |
| charts | Typed chart results with their availability and evidence |
| largest_inflows, largest_outflows | Separate bank rankings of up to five positive credits/debits |

Bank metadata includes the source currency and period boundaries. Its company,
reporting_date and unit_scale are null. Balance metadata includes the source
company, currency, reporting_date and unit_scale. Its bank period dates are null.

An analysis contains workspace_id, document_type, currency, reliability, metrics
and warnings. Each metric contains key, value, unit, status, reason,
calculation_id and source_refs.

A chart contains key, unit, status, reason and series. Each series has key, label
and points. A point has label, value, reason and source_refs. ISO dates use
YYYY-MM-DD and months use YYYY-MM. Category and snapshot labels are named below.

A ranking entry contains amount, unit, date, description and source_refs.
Entries sort by amount descending, date ascending and original source row
ascending. Balance sheets return empty rankings.

## Metrics

| Document | Metric keys |
| --- | --- |
| Bank | total_credit, total_debit, net_cash_flow, opening_balance, closing_balance, average_balance |
| Balance | working_capital, balance_difference, current_ratio, debt_to_equity |

Existing metrics retain their original bank.*.v1 or balance_sheet.*.v1 calculation
IDs. New IDs are `dashboard.average_balance.v1` and
`dashboard.debt_to_equity.v1`.

Average balance is the sum of each verified end-of-day balance multiplied by
the number of days it applies, divided by the inclusive statement duration.
It requires both period boundaries, opening/closing balances and a uniquely
supported running-balance sequence. Verified balances carry forward across days
without transactions. Ambiguous order or incomplete coverage makes it unavailable.
Known nonfinancial export notes do not block it. Ambiguous rows and notices
containing numeric content remain unavailable.

Debt-to-equity uses the sum of canonical short_term_borrowings and
long_term_borrowings, divided by reported total equity. The classified liability
leaves must account for the reported liability total before an absent borrowing
category can contribute zero. Missing amounts or classifications, missing
currency/scale, or zero equity make the ratio unavailable. Negative equity keeps
its sign and produces a warning.

## Chart keys and values

| Chart key | Series keys | Point labels |
| --- | --- | --- |
| daily_flows | credit, debit, net_flow | Observed transaction dates |
| monthly_flows | credit, debit, net_flow | Observed transaction months |
| daily_balances | balance | Verified balance dates and applicable period boundaries |
| debit_categories | debit | Category names |
| reported_totals | reported | assets, liabilities, equity |
| balance_components | components | assets_current, assets_non_current, liabilities_current, liabilities_non_current |

Bank flow charts group all saved rows. A month may have only partial statement
coverage. Omitted dates/months are gaps and are not asserted to have zero flow.
Use a step line for an available daily_balances chart because verified balances
carry forward between points.

Balance charts are current-period snapshots. Reported totals stay separate from
leaf breakdowns. A breakdown is unavailable unless its classified leaf values
cover the reported section. Prior-period values, notes and subtotals stay in the
stored source record and are excluded from current leaf sums.

Debit categories use the first whole-word or phrase match in this order.

| Category | Keywords |
| --- | --- |
| food | grocery, groceries, restaurant, cafe, swiggy, zomato |
| housing | rent, hostel, housing |
| transport | bus, metro, taxi, uber, ola, petrol, fuel |
| shopping | shopping, amazon, flipkart, clothing |
| utilities | electricity, water bill, broadband, internet, recharge |
| education | tuition, school, college, textbook |
| entertainment | cinema, movie, netflix, spotify |
| cash_withdrawal | atm, cash withdrawal |
| transfers | transfer, neft, imps, rtgs |
| other | Unmatched descriptions, including UPI alone |

These labels approximate purpose from descriptions. Category amounts reconcile to
the eligible debit total. An available category series may have no points when
the statement has no positive debits.

## Units, missing values and evidence

Monetary metrics and chart values are JSON numbers in base source currency.
Balance-sheet amounts are multiplied by unit_scale once. Ratios use unit
`ratio` and are unscaled. Frontend code should display the returned amounts
without applying unit_scale again. Currency preferences do not convert them.

Null means unavailable and must have an explanation where a metric or point is
missing. Zero and negative values remain numeric values. An unavailable chart
has a reason and an empty series. An available chart may contain some null points.

Show analysis.reliability and analysis.warnings with the charts. Reliability is
valid, unreliable or insufficient_data. A 200 response can describe unreliable
or incomplete data. Reported mismatches are preserved.

Each source reference contains the original document_id, sheet_name,
source_rows and field_paths. Rows are 1-based original CSV records or worksheet
rows. Paths use original indices in the complete parsed document. References
do not manufacture transaction IDs or provide source download URLs.

The backend uses Decimal and preserves exact numeric tokens in JSON. JavaScript
Number has finite precision. Use a decimal-capable JSON parser if the frontend
needs to preserve every digit, and leave financial calculations to the backend.
Repeating ratios and averages use at least 38 significant Decimal digits.

## Errors

Expected domain errors use `detail.code` and `detail.message`.

| HTTP status | Code and behavior |
| --- | --- |
| 401 | unauthorized. Reauthenticate. WWW-Authenticate is Bearer. |
| 404 | workspace_not_found for either a missing or foreign workspace |
| 409 | document_not_ready for an owned document that has not parsed |
| 422 | FastAPI validation detail array for an invalid UUID |
| 503 | auth_unavailable, database_unavailable or dashboard_unavailable |

An incomplete parsed document returns 200 with warnings and unavailable
sections. A pending failed upload has an unready document until recovery
settles it. A cleaned upload's removed workspace returns 404.

## Verification and review

From `backend` with the local SQL test dependencies installed, run:

```powershell
.\.venv\Scripts\python.exe scripts/verify_sprint2.py
.\.venv\Scripts\python.exe -m pytest -q verification/test_balance_parser_persistence.py verification/test_owned_analysis_api.py
```

Dashboard integration checks use the actual supported CSV/XLSX parsers, public
upload and dashboard routes, owned reader, and migrated local PostgreSQL/RLS.
They cover both bank and balance layouts, source references, metadata gaps,
unreconciled figures, exact saved values, repeated GETs and two users. They assert
that dashboard reads change neither the saved financial rows and attempt journal
nor the source bytes. Existing deletion and generation-barrier tests run in the
combined suite.

A8 verification passed 1,363 backend tests with zero skips and one existing
TestClient deprecation warning. The six explicit acceptance checks, all eight SQL
suites, catalog audit, lint, formatting, dependency checks and existing API
readiness checks passed.

Auth and Storage HTTP are simulated. Hosted Supabase verification, independent
database-session contention and team review remain pending. No live AI call is
needed for dashboard calculations.

Shreyav reviews integration and owns hosted checks and the final integration PR.
AI + Analysis reviews formulas, debt coverage, chronology and category rules.
Frontend reviews the examples, null handling, chart rendering and numeric precision.
