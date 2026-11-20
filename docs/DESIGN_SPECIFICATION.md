# FIN GENIE — COMPLETE FINTECH WEB APPLICATION UI/UX DESIGN & ARCHITECTURE SPECIFICATION

> **Author**: Senior Fintech UX Architect, Product Designer & Full-Stack Engineer  
> **Application**: FinGenie (India)  
> **Target Audience**: Individuals and Small Businesses / Freelancers in India  
> **Platform**: Desktop Web (1440 × 900 px baseline), Tablet & Mobile Adaptive  
> **Database & Auth**: Supabase (PostgreSQL, Row Level Security, Supabase Auth)  

---

## 1. Executive Summary & Design Objective

FinGenie is a premium, modern, intelligent financial-analysis web application designed specifically for the Indian market. It bridges the gap between raw, opaque banking statement files (CSV/XLSX) and clear financial understanding by pairing calculated financial metrics with natural language AI explanations and strict data-source traceability.

The application adheres strictly to Indian financial conventions:
- **INR Currency Display**: `₹1,25,000.00`
- **Indian Numbering System**: Thousands (`K`), Lakhs (`L`), and Crores (`Cr`)
- **UPI Narrations & Bank Channels**: Categorization for UPI, NEFT, RTGS, IMPS, Card POS, ATM withdrawals, and NetBanking autopays
- **Credit & Debit Classification**: Emerald green (`#1D8A60`) for positive inflows, Soft Red (`#C94C4C`) for outflows
- **Traceability Guarantee**: Every calculated KPI links directly to the source file name and line row (`#row-142` in `HDFC_Statement_Oct2026.csv`).

---

## 2. Visual Identity & Design Tokens System

### 2.1 Color Palette
The color system emphasizes trust, composure, and financial clarity:

| Token | Hex | Role & Application |
|---|---|---|
| **Deep Forest Green** | `#10251E` | Primary brand emphasis, dark headers, brand hero panels |
| **Emerald Green** | `#1D8A60` | Primary actions (CTAs), positive cash flow, active navigation pills |
| **Pale Mint** | `#E7F4EC` | Soft highlights, selected bank cards, active menu backgrounds |
| **Warm Off-White** | `#F5F7F5` | Main application shell and background canvas |
| **Pure White** | `#FFFFFF` | Cards, ledger table rows, modals, form inputs |
| **Charcoal** | `#202923` | High-contrast page titles, transaction amounts, primary text |
| **Muted Grey** | `#68746D` | Secondary labels, timestamps, file metadata, helper text |
| **Light Grey-Green**| `#E1E8E2` | Hairline dividers, card outlines, table borders |
| **Soft Red** | `#C94C4C` | Outflows/debits, destructive confirmations, validation errors |
| **Amber** | `#D99A32` | Warnings, duplicate file notices, pending upload status |

### 2.2 Typography Scale (Inter / Manrope)
- **KPI Display Hero**: `32px` (Bold 700, -0.6px letter spacing)
- **H1 Page Headings**: `28px` (Bold 700, -0.5px letter spacing)
- **H2 Section Headings**: `20px` (Semi-bold 600, -0.3px letter spacing)
- **Card Titles & Subheaders**: `15px` (Semi-bold 600)
- **Body Text**: `14px` (Regular 400 & Medium 500, line-height 1.5)
- **Secondary & Table Meta**: `12px – 13px` (Medium 500)
- **Micro Tags & Row Tags**: `11px` (Bold 700, uppercase letter-spacing 0.5px)

### 2.3 Layout, Spacing & Elevation
- **Spacing Grid**: 8px baseline (`8px`, `16px`, `24px`, `32px`, `40px`, `48px`)
- **Corner Radii**: Cards (`14px`), Inputs/Buttons (`10px`), Badges (`9999px`)
- **Elevation**:
  - Cards: `0 2px 8px rgba(16, 37, 30, 0.05)`
  - Drawers: `-4px 0 24px rgba(16, 37, 30, 0.12)`
  - Floating Overlays: `0 10px 25px -5px rgba(16, 37, 30, 0.08)`

---

## 3. Application Architecture & Shared Navigation Shell

All authenticated screens share a consistent, high-efficiency two-column frame layout:

```
+-------------------+---------------------------------------------------------+
| FIN GENIE         | Top Navigation: Title | Bank Badge | Search | Upload CTA|
| [Traj Icon]       +---------------------------------------------------------+
|                   |                                                         |
| 1. Home           | Main Content Canvas                                     |
| 2. Financial Dash | (KPI Cards Grid / Multi-filter Ledger / AI Chat)        |
| 3. Transactions * |                                                         |
| 4. AI Assistant   |                                                         |
| 5. Chat History   |                                                         |
| ----------------- |                                                         |
| 6. Settings       |                                                         |
| 7. Help & Support |                                                         |
| ----------------- |                                                         |
| [User Card & Out] |                                                         |
+-------------------+---------------------------------------------------------+
```

### 3.1 Persistent Left Sidebar (240px)
- Fixed left sidebar with brand icon and wordmark
- Strict navigation ordering:
  1. **Home** (Upload card & recent chat summaries)
  2. **Financial Dashboard** (KPI cards, cash flow charts, AI insights)
  3. **Transactions** (High-density financial ledger)
  4. **AI Assistant** (Conversational financial intelligence)
  5. **Chat History** (Searchable past conversations)
  *Divider*
  6. **Settings** (Account, Security, Bank preferences, Retention)
  7. **Help & Support** (FAQs, documentation, calculation transparency)
- Bottom profile summary card: User avatar initials, full name, Account Type badge (`Personal` vs `Business`), Bank indicator (`HDFC Bank`), and logout trigger.

### 3.2 Top Navigation Bar (70px)
- Breadcrumb trail (`FinGenie / Transactions`)
- Active document and institution chip (`HDFC Bank • HDFC_Statement_Oct2026.csv`)
- Global search input with instant matching
- Notification bell with unread dot
- Primary CTA: "Upload statement" button

---

## 4. Screen-by-Screen Detailed Specifications

### Frame A: Login Screen
- **Split-Screen Design**:
  - Left panel: Deep forest green brand hero with upward trajectory graphic, value proposition ("Your finances, finally in focus"), floating preview metric cards (`₹1,25,000.00` net inflow), and 256-bit encryption assurance.
  - Right panel: White card with email address, password input with show/hide eye toggle, remember me checkbox, forgot password link, primary "Log in to FinGenie" button, and "Continue with Google" SSO.
- **States**: Default, invalid email, incorrect credentials alert, loading spinner, and success redirect.

### Frame B: Sign-Up & Indian Bank Onboarding Flow
- **Multi-Step Guided Flow**:
  - **Step 1 (Account Credentials)**: Full name, email, password, confirm password, terms checkbox.
  - **Step 2 (Account Type)**: Selectable Personal vs Small Business cards.
  - **Step 3 (Searchable Indian Bank Selection)**:
    - Search field with real-time filtering
    - Supported banks: State Bank of India (SBI), HDFC Bank, ICICI Bank, Axis Bank, Kotak Mahindra Bank, Bank of Baroda (BOB), Punjab National Bank (PNB), IndusInd Bank, and Other Bank option.
    - Explicit disclaimer: *"Selecting a bank identifies the institution format of your records. FinGenie does not connect to or link your live bank account."*
  - **Step 4 (Finish Onboarding)**: Animated checkmark, summary of profile, and direct CTA to workspace.

### Frame C: Home Screen / Workspace
- **Upload Document Card**: Drag-and-drop dropzone supporting CSV and XLSX files. Clear document slots for Personal (Bank Statement) and Business (Bank Statement + Balance Sheet).
- **Recent Financial Analyses Table**: Document name, bank institution, upload date, processing status, and "Open dashboard" action.
- **Recent AI Conversations**: Previews of previous assistant queries ("Why did my dining expenses increase?", "Summarize October cash flow") with "Continue conversation" links.

### Frame D: Upload & Processing Workflow
- **10 Distinct Lifecycle States**:
  1. Empty dropzone
  2. File selected with size & format badge
  3. Upload in progress with percentage bar
  4. Header & column detection verification (Date, Narration, Debit, Credit, Balance)
  5. Processing & metric aggregation
  6. Success confirmation with "View Dashboard" button
  7. Unsupported format error (e.g. PDF rejected with clear guidance)
  8. Malformed or empty CSV error
  9. Duplicate statement detected warning
  10. Network failure with retry trigger.

### Frame E: Financial KPI Dashboard
- **Header**: Active period selector, comparison toggle ("vs previous month"), last updated timestamp, export report button, and "Ask FinGenie" shortcut.
- **4 Primary KPI Cards**: Total Money In (Credits), Total Money Out (Debits), Net Cash Flow, and Closing Balance.
- **Visualizations**: Cash flow area chart, spending category breakdown donut/bars, monthly comparison bars.
- **FinGenie AI Insights Panel**: 3-4 grounded observations with "Inspect supporting transactions" links.

### Frame F: Transactions (Ledger & Inspector)
- **High-Density Ledger Table**: Date, Narration, Category tag, Channel badge (UPI, NEFT, IMPS, RTGS, Card, ATM), Debit, Credit, and Running Balance.
- **KPI Summary Header**: Filtered total credits, debits, net delta, and record count.
- **Filter Toolbar**: Free-text keyword search, type buttons (All / Credit / Debit), category dropdown, channel dropdown, amount threshold filters, and "Reset filters" chip.
- **Sorting & Pagination**: Column sort by date or amount, previous/next page navigation.
- **Transaction Detail Drawer**: Slide-out drawer displaying full un-truncated narration, exact source file name, row number reference (`#row-142`), AI-inferred badge vs ground truth indicator, and "Ask FinGenie about this transaction" button.

### Frame G: AI Financial Assistant
- Two-column chat interface: Left conversational thread with markdown responses, tables, and inline currency tokens; Right contextual panel displaying active statement summary and metric highlights.
- Suggested prompt pills: "Explain my cash-flow trend", "What were my largest expenses?", "Summarize my monthly UPI payments".

### Frame H: Chat History
- Searchable list of past conversations with timestamps, associated statement documents, and resume buttons.

### Frame I: Settings & Security
- Tabs: Profile (Name, Email, Account Type), Security (Change password with current/new/confirm fields and validation rules), Bank Preferences, and Data Privacy (document deletion & account removal).

### Frame J: Password Recovery
- Minimalist password reset flow with email submission, validation, and confirmation state.

### Frame K: Help & Support
- FAQs, calculation methodologies, source-data traceability explanations, and troubleshooting guide for CSV exports.

---

## 5. Prototype Flows & User Journeys

1. **New User Onboarding**: Login → Sign Up → Personal Account → HDFC Bank → Complete Onboarding → Home Workspace.
2. **First Analysis**: Home Workspace → Upload CSV → Confirm Column Mapping → Processing → Financial Dashboard.
3. **Transaction Inspection**: Dashboard → View All Transactions → Filter by "UPI" & "Dining" → Click Row → Open Detail Drawer → Verify `#row-142` in `HDFC_Statement_Oct2026.csv`.
4. **AI Assistant Inquiry**: Drawer → "Ask FinGenie" → AI summarizes transaction frequency and trend → Click "Supporting records".
5. **Security Management**: Sidebar → Settings → Security → Change Password → Save Changes Toast.

---

## 6. Implementation Quality & Testing Verification

The codebase includes full unit and integration test coverage (`tests/formatters.test.js`, `tests/auth.test.js`, `tests/transactions.test.js`):
- Formatters: Indian numbering grouping (Lakhs & Crores), standard INR formatting (`₹1,25,000.00`), negative values, and date parsing.
- Auth & Onboarding: RFC email validation, password strength rules, bank search engine, mock/live Supabase authentication, and multi-step onboarding progression.
- Transactions & Ledger: Multi-parameter filtering, sorting arithmetic, pagination bounds, KPI calculations, and CSV export formatting.
