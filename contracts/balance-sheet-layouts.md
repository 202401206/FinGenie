# Balance Sheet Layouts & Extraction Contract

Agreed parsing contract for FinGenie Sprint 2 balance sheet parsers. This specification covers both Layout A (single-period) and Layout B (comparative), supported file formats (CSV and XLSX), extraction rules, metadata aliases, and unmapped reason codes.

---

## 1. Supported Layout Matrix

| Attribute | Layout A (Single-Period) | Layout B (Comparative) |
| :--- | :--- | :--- |
| **Header Columns** | `Particulars,Amount` | `Particulars,[Note No],<YYYY-MM-DD>,<YYYY-MM-DD>` |
| **Note Column** | N/A | Optional (`Note No`, `Note`, `Notes`) |
| **Period Columns** | Single amount column | Two or more dated columns (ISO `YYYY-MM-DD` or delimited `DD/MM/YYYY`) |
| **Period Selection** | Extracted directly | Deterministically selects the column matching declared `reporting_date` |
| **Prior Period Handling** | N/A | Preserved separately in `unmapped` with `reason="prior_period_value"` |
| **Supported File Formats** | CSV (`.csv`) and XLSX (`.xlsx`) | CSV (`.csv`) and XLSX (`.xlsx`) |

---

## 2. Metadata Extraction & Aliases

Metadata may appear in the preamble rows preceding the main statement table:

| Field | Recognized Label Aliases | Value Format / Constraints |
| :--- | :--- | :--- |
| **Company** | `Company`, `Company Name`, `Entity`, `Organization`, `Name of Company` | String. May be null/unknown if absent from preamble. |
| **Reporting Date** | `Reporting Date`, `As at`, `As on`, `Balance Sheet as of`, `Period Ended`, `Date` | Required unambiguous date (`YYYY-MM-DD`). |
| **Currency** | `Currency`, `Reporting Currency`, `Curr` | Supported initial codes: `INR` (Indian Rupees / ₹), `USD` (US Dollars / $). Missing/ambiguous stays null. Conflicting raises 422. |
| **Unit Scale** | `Amounts In`, `Scale`, `Units in`, `In`, `Figures in` | Integer multiplier: `units`/`actuals` = 1, `thousands` = 1,000, `lakhs` = 100,000, `millions` = 1,000,000, `crores` = 10,000,000. |

---

## 3. Section Labels & Canonical Fields

Financial items are deterministically classified based on standard section headings and leaf item labels:

### Assets (`assets`)
* **Current Assets (`assets.current`):**
  * Section headings: `Current Assets`, `I. Current Assets`, `Assets - Current`
  * Canonical items:
    * `cash`: `Cash`, `Cash and Cash Equivalents`, `Cash & Bank`, `Bank Balances`
    * `receivables`: `Trade Receivables`, `Receivables`, `Accounts Receivable`, `Debtors`, `Sundry Debtors`
    * `inventory`: `Inventories`, `Inventory`, `Stock`, `Stock-in-trade`
    * `other_current_assets`: `Other Current Assets`, `Prepaid Expenses`, `Short-term Loans and Advances`
* **Non-Current Assets (`assets.non_current`):**
  * Section headings: `Non-Current Assets`, `Fixed Assets`, `Non Current Assets`
  * Canonical items:
    * `property_plant_equipment`: `Property, Plant and Equipment`, `Property Plant and Equipment`, `Equipment`, `Fixed Assets`, `Tangible Assets`, `PPE`
    * `intangible_assets`: `Intangible Assets`, `Goodwill`
    * `non_current_investments`: `Non-Current Investments`, `Long-term Investments`, `Investments`
    * `other_non_current_assets`: `Other Non-Current Assets`, `Long-term Loans and Advances`
* **Reported Total (`assets.total`):**
  * Labels: `Total Assets`, `Total Current & Non-Current Assets`

### Liabilities (`liabilities`)
* **Current Liabilities (`liabilities.current`):**
  * Section headings: `Current Liabilities`, `Liabilities - Current`
  * Canonical items:
    * `trade_payables`: `Trade Payables`, `Payables`, `Accounts Payable`, `Creditors`, `Sundry Creditors`
    * `short_term_borrowings`: `Short-Term Borrowings`, `Short Term Debt`, `Short-term Loans`
    * `other_current_liabilities`: `Other Current Liabilities`, `Accrued Expenses`, `Provisions`
* **Non-Current Liabilities (`liabilities.non_current`):**
  * Section headings: `Non-Current Liabilities`, `Long-Term Liabilities`
  * Canonical items:
    * `long_term_borrowings`: `Long-Term Borrowings`, `Long-term loan`, `Long-Term Debt`, `Bonds Payable`
    * `other_non_current_liabilities`: `Other Non-Current Liabilities`, `Deferred Tax Liabilities`
* **Reported Total (`liabilities.total`):**
  * Labels: `Total Liabilities`, `Total Current & Non-Current Liabilities`

### Equity (`equity`)
* Section headings: `Equity`, `Shareholders' Funds`, `Stockholders' Equity`, `Capital and Reserves`
* Canonical items:
  * `share_capital`: `Share Capital`, `Common Stock`, `Equity Share Capital`, `Contributed Capital`
  * `retained_earnings`: `Retained Earnings`, `Reserves and Surplus`, `Surplus`, `Accumulated Deficit`, `Accumulated Losses` (Negative values permitted)
* **Reported Total (`equity.total`):**
  * Labels: `Total Equity`, `Total Shareholders' Funds`, `Total Equity and Reserves`

---

## 4. Unmapped Reason Codes

Unrecognized rows, metadata conflicts, or prior period values are preserved in `unmapped` using one of these standard reason codes:

| Reason Code | Trigger / Meaning |
| :--- | :--- |
| `unrecognized_financial_item` | Financial line item that does not match a known canonical field or section. |
| `unrecognized_note` | Informational text, notes, or disclaimers in the statement table. |
| `reported_subtotal` | Section subtotal (e.g. `Total Current Assets`) preserved separately so leaf items are never double-counted. |
| `prior_period_value` | Amount belonging to a prior comparative period (Layout B). Formatted as `<Date>: <Amount>`. |
| `ambiguous_currency` | Currency declaration could not be matched unambiguously to supported codes. |
| `ambiguous_unit_scale` | Unit scale text could not be resolved to a supported integer multiplier. |

---

## 5. Numeric & Traceability Rules

1. **Exact Decimals in Reported Units:**
   * Money is stored as `Decimal` in reported units.
   * The parser does **NOT** multiply values by `unit_scale`; scaling occurs exclusively in analysis.
2. **Missing vs. Zero:**
   * Missing or empty cells remain `None` (`null`). Zero is never fabricated.
   * Real zero reported in the source remains `Decimal("0")`.
3. **No Floats or Booleans:**
   * `float` arithmetic is forbidden. Booleans (`True`/`False`) are rejected.
4. **Source Row Provenance:**
   * Every line item and metadata entry records its 1-based original CSV record or Excel row (`source_row` > 0).
5. **Resource Limits:**
   * File size: 5 MiB max.
   * XLSX expanded container: 25 MiB max, 500 archive entries max. Macro-enabled workbooks (`.xlsm`) strictly rejected.
   * Grid bounds: 50 columns max, 20,000 rows max.
   * Formulas: Formulas in financial or date cells are strictly rejected (`InvalidStatementError`).
