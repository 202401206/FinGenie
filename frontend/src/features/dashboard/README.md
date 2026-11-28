# Person 3: Dashboards, Charts and Transaction Exploration

## Module Overview
This directory implements the Person 3 frontend ownership for **FinGenie**, delivering:
- `/workspaces/:workspaceId/dashboard` route component (`DashboardPage.jsx`).
- Dynamic support for both **Bank Statements** (`BankDashboardView.jsx`) and **Balance Sheets** (`BalanceSheetDashboardView.jsx`).
- Deterministic analysis metrics without client-side financial recalculations.
- Server-paginated transaction exploration with row-level provenance (`TransactionExplorer.jsx`).
- Verified metric visualizations and evidence query routing (`?documentId=...&sourceRow=...`).
- Explicit user-triggered AI executive summary mount (`FinancialSummaryMount.jsx`).
- Offline development fixtures (`src/mocks/dashboard/`).

---

## Architecture Boundaries & Single-Writer Rules
- **Owned Files:** `src/features/dashboard/`, `src/mocks/dashboard/`, and `tests/dashboard_*.test.js`.
- **Backend API Contract:**
  - `GET /workspaces/{id}/analysis` -> Fetches verified Python calculation results.
  - `GET /workspaces/{id}/transactions` -> Bank statements only (returns 409 for balance sheets).
- **Teammate Integration:**
  - Integrates with Person 1's shared workspace context and route registration.
  - Honors Person 1's `useFinancialData()`: `deletionPending` suspends financial displays and mutations.
  - Embeds Person 4's `<FinancialSummary workspaceId={workspaceId} />` with strict failure isolation.

---

## 6 Completed Milestones

1. **`feat(dashboard): add workspace dashboard views and fixtures`**
   - Built bank/balance sheet view variants, metric cards, reliability banner, and mock fixtures.
2. **`feat(dashboard): connect saved workspace analysis`**
   - Integrated `GET /workspaces/{id}/analysis` with `useDashboardAnalysis` hook and race-condition guards.
3. **`feat(dashboard): add paginated transaction exploration`**
   - Added bank-only transaction ledger with server pagination bounds and audit drawer.
4. **`feat(dashboard): visualize verified metrics and source evidence`**
   - Added responsive SVG/CSS metrics charts and evidence query parameter handling (`?sourceRow=...`).
5. **`feat(dashboard): integrate verified AI summary panel`**
   - Mounted user-triggered AI summary panel, isolated summary errors, and added pending-deletion state.
6. **`test(dashboard): verify financial display and workspace isolation`**
   - Comprehensive behavioral tests verifying zero/negative values, no double unit scaling, and state isolation.
