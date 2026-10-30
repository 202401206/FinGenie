# Shared contracts

A contract is an agreed data shape at a team boundary. These documents let teams
work independently. They do not implement parsers, schemas or planned endpoints.
`GET /api/health` and `GET /api/me` are live. The document/analysis shapes below are a **proposal for
affected-team review**, based on the supplied brainstorming PDF and user request.

- [Endpoint plan and payloads](api/README.md)
- [Bank statement example](examples/bank-statement.json)
- [Balance sheet example](examples/balance-sheet.json)
- [Bank analysis example](examples/financial-analysis.json)
- [Balance-sheet analysis example](examples/balance-sheet-analysis.json)

All examples are hand-authored, synthetic fixtures; they are not output from an
implemented parser or calculation engine and contain no real account data.

## Original requirements from the PDF

PDF pp. 3-4 define these fields; keep their names when implementing schemas:

| Document | Required shape to preserve |
| --- | --- |
| Bank statement | `bank`, `account_holder`, `account_type`, `currency`, `period_start`, `period_end`, `opening_balance`, `closing_balance`, `transactions`, `unmapped` |
| Transaction | `date`, `description`, `debit`, `credit`, `balance`, `source_row` |
| Balance sheet | `company`, `reporting_date`, `currency`, `unit_scale`, `assets`, `liabilities`, `equity`, `unmapped` |
| Assets/liabilities | `current` and `non_current` line-item arrays, `total` |
| Line item | `canonical_field`, `raw_label`, `value`, `source_row` |
| Equity | `share_capital`, `retained_earnings`, `total` |

The PDF requires unknown data preservation (`unmapped`), source traceability,
balance-sheet reconciliation and unit scaling. Bank metadata above the header may
be missing. It does not define a full analysis-response schema, null semantics,
row indexing or pagination. These are proposed below, not original requirements.

## Proposed data conventions

- User types: `personal`, `business`. Document types: `bank_statement`, `balance_sheet`.
  Only business users may upload balance sheets. Validate on the server as well as UI.
- Dates: ISO `YYYY-MM-DD`. Missing optional metadata or amounts use `null`, never a
  fabricated zero or empty date. Arrays use `[]`. A real zero remains `0`.
  Required transaction fields missing after mapping produce a validation error;
  never silently skip malformed financial rows. Nontransaction rows may be classified
  and preserved in `unmapped` when unrecognized.
- Amount fields remain JSON numbers as in the PDF. Parse using decimal-aware Python
  handling for money (`Decimal`); avoid binary float arithmetic for financial results.
  JS numbers are for display; the frontend never computes authoritative KPIs.
  Precision, serialization limits and per-metric rounding still need review.
- `debit` and `credit` are nonnegative magnitudes; zero means no movement on that side.
  Agree reversal/negative-balance handling per bank before implementing mapping.
- `source_row` is a **1-based original spreadsheet row or CSV record**, including
  preamble and headers. It is never a filtered DataFrame index. For CSV, a quoted
  multiline record counts once, rather than as multiple physical text lines.
- Proposed `source_metadata`: `{document_id, sheet_name}`. CSV uses `null` sheet;
  XLSX uses the selected sheet's exact name. V1 examples use one sheet; reject or
  explicitly select among ambiguous sheets until multi-sheet handling is agreed.
- Proposed `source_locations` maps scalar field paths to `{source_row}`. This adds
  traceability to opening/closing balances, totals and equity while preserving the
  PDF's scalar shape. Sheet and document are inherited from `source_metadata`.
  If a scalar is derived instead of reported, retain all contributing row references
  in calculation metadata; do not invent a single source row.
- Proposed `unmapped` entries: `{source_row, raw_label, raw_value, reason}`. Preserve
  unknown source content and its location without exposing it in logs. Public
  fixtures use synthetic content. Multi-column unknowns may need a reviewed extension.
- Balance-sheet values, totals and equity stay in **reported units**. `unit_scale`
  multiplies them into base currency: `1` = units, `1000` = thousands, `100000` = lakhs,
  `10000000` = crores. Do not rescale stored values and also apply the multiplier.
  Unknown scale/currency blocks affected monetary KPIs pending user clarification.

## Proposed analysis result

Envelope: `workspace_id`, `document_type`, `currency`, `reliability`, `metrics`,
`warnings`. `reliability` is `valid`, `unreliable` or `insufficient_data`.
Each metric has `key`, numeric-or-null `value`, `unit`, `status`
(`available`/`unavailable`), nullable `reason`, `calculation_id`, `source_refs`.
Each source reference has `document_id`, `sheet_name`, `source_rows` and
`field_paths` pointing into the standardized JSON. Calculation IDs identify a
reviewed definition/version; they are not callable code or provider function names.

For fixture review only: bank totals are 5000 credit, 2500 debit and 2500 net;
10000 opening + 2500 net = 12500 closing. Balance-sheet totals are
300 = 120 + 180 in reported units. Working capital is
(100 + 50 - 80) * 100000 = 7000000 INR. Analysis money is always base currency;
ratios use `unit: "ratio"` and no scale multiplier on the ratio itself.

Missing required inputs or zero denominators give an unavailable metric with
`value: null` and a reason, never infinity or invented results. A reconciliation
failure marks the result unreliable with a warning; decide per metric whether it
can be shown. Define average-balance weighting, debt components and rounding before
implementing those KPIs. Not all liabilities necessarily count as debt.

Every future AI numeric claim must match a calculation/tool result and cite its
calculation ID and source references. Numeric text validation, retry limits and
safe failure behavior must be tested before AI endpoints are considered done.

## Change process

Endpoint changes: Backend + Frontend review. Document/metric changes: Backend +
AI + Analysis review, plus Frontend when consumed there. Update docs, examples,
future Pydantic models and affected tests together. The PDF's field names must
not be silently renamed. No financial schema models are implemented in this commit.
