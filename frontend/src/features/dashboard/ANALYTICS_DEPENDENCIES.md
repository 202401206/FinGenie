# Dashboard Analytics Dependencies & Status Specification

**Document Owner:** Person 3 (Dashboards, Charts and Transaction Exploration)  
**Target Milestone:** Sprint 2 / Sprint 3  
**Status Date:** November 28, 2026  

---

## 1. Supported & Implemented Analytics

The following endpoints and metrics are fully supported, verified, and rendered deterministically:

| Document Type | Endpoint | Supported Metric Keys | Unit | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Bank Statement** | `GET /workspaces/{id}/analysis` | `total_credit`, `total_debit`, `net_cash_flow` | Currency (e.g. `INR`) | Implemented & Live |
| **Bank Statement** | `GET /workspaces/{id}/transactions` | Paginated transactions (`debit`, `credit`, `balance`, `source_row`) | Base Currency | Implemented & Live |
| **Balance Sheet** | `GET /workspaces/{id}/analysis` | `working_capital`, `balance_difference`, `current_ratio` | Currency / Ratio | Implemented & Live |

---

## 2. Pending Analytics & Backend Dependencies

In accordance with Person 3 architectural requirements, the frontend **does not fabricate** client-side calculations or mock time-series for unsupported analytics. The following capabilities are pending backend implementation:

### 2.1 Category Spending Classifications
- **Current State:** Backend parsers extract description strings (e.g. `UPI/Swiggy`, `TCS Salary`), but do not yet expose standardized category taxonomy.
- **Backend Requirement:** An endpoint or enrichment in `GET /workspaces/{id}/analysis` returning `categories: [{ id, name, total_debit, percentage }]`.
- **Frontend Readiness:** `DashboardPage` includes an honest availability notice informing users that category aggregations will automatically render once backend classification endpoints are mounted.

### 2.2 Projections & Cash Flow Forecasts
- **Current State:** `GET /workspaces/{id}/projections` is proposed in architecture docs but has no mounted route in the FastAPI backend router (`app/api/router.py`).
- **Backend Requirement:** Deterministic projection engine requiring minimum 3 months of historical statements, returning projected monthly points, method, and confidence intervals.
- **Frontend Policy:** Strict refusal to invent client-side projections. No forecast is rendered until the backend route is published and peer-reviewed.

### 2.3 Opening / Closing Balances & Variance Flags
- **Current State:** Backend analysis functions (`bank.opening_balance.v1`, `bank.closing_balance.v1`) exist in `bank_kpis.py`, but are optional in public analysis response envelopes.
- **Frontend Handling:** `MetricCard` gracefully displays these cards if returned in `metrics[]` without crashing on unknown keys.
