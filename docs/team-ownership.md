# Team ownership

There are exactly three teams. Product Owner, Scrum Master and reviewers are roles
within these teams, not extra development teams.

| Team | Owns | Responsibilities |
| --- | --- | --- |
| Frontend | `frontend/` | Auth UI, upload UI, transaction table, dashboards/charts, chat UI, API integration |
| Backend | `backend/app/api/`, `core/`, `schemas/`, `services/`, `parsers/`, `db/`; `supabase/migrations/` | Endpoints, auth verification, file validation/parsing, database/storage, integration |
| AI + Analysis | `backend/app/analysis/`, `backend/app/ai/` | Bank KPIs, balance-sheet ratios, categories, projections, summaries, chat, tools, number guard and traceability |

Tests follow the corresponding module owner: Backend owns `tests/api` and
`tests/parsers`; AI + Analysis owns `tests/analysis` and `tests/ai`.
Root tooling, `app/main.py`, docs and contracts are shared coordination points.
The team leader coordinates reviews; no automatic CODEOWNERS rules are installed.

## Work independently

- Frontend: use the synthetic JSON in `contracts/examples/` for feature development.
  See `frontend/src/mocks/README.md`. The app can start without FastAPI or Supabase.
- Backend: use synthetic parser fixtures and TestClient tests. No UI dependency.
- AI + Analysis: pass fixture data directly to pure functions and test with pytest.
  No Supabase or LLM connection is needed for deterministic analysis. Mock provider
  calls in AI tests later; do not build a second server.

## Review shared changes

Changes to endpoints need Backend and Frontend review. Changes to parsed JSON or
analysis results need Backend and AI + Analysis review, plus Frontend when displayed
or consumed there. Affected teams review Pydantic schema changes as well.
Update contract docs, examples and consumers in the same PR or agree a staged change.

## First assignments after setup

1. Frontend: sketch the Sprint 1 auth/upload/table flow and agree mock responses.
2. Backend: specify file validation, supported bank formats, ownership checks and the
   first parser test fixtures; review the proposed database before writing SQL.
3. AI + Analysis: define the total-credit/debit KPI contract and tests with source
   rows; then implement pure functions. Agree missing-data and rounding policies.

Before feature work, assign a sample-file steward, choose the first 2-3 banks and
review the proposed contracts together. Balance-sheet parsing and KPIs belong to
Sprint 2; chat and projections belong to Sprint 3.
