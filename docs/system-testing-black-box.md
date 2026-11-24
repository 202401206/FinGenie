# FinGenie System Testing Specification: Black-Box & Acceptance Test Suite

> **Document Type:** System-Level Black-Box Testing & Acceptance Specification
> **Application:** FinGenie Financial Analytics Platform
> **Target Subsystem:** Bank Statement Analytics & KPI Calculation Engine
> **Reference Module:** [`backend/app/analysis/bank_kpis.py`](../backend/app/analysis/bank_kpis.py)
> **Reference Contracts:** [`contracts/README.md`](../contracts/README.md), [`contracts/examples/bank-statement.json`](../contracts/examples/bank-statement.json), [`contracts/examples/financial-analysis.json`](../contracts/examples/financial-analysis.json)
> **Status:** Proposed Specification & Test Plan (Sprint 2 Milestone)

---

## 1. Purpose and Scope of Black-Box Testing

### 1.1 Purpose
The purpose of this document is to specify a rigorous, exhaustive **black-box testing suite** for the FinGenie Bank Statement Analytics subsystem. Black-box testing evaluates system behavior exclusively against external specifications, functional requirements, and agreed JSON contracts—without inspecting or relying upon internal code paths, control flows, or language-specific constructs.

In financial software, black-box testing provides the final barrier against computational inaccuracies, subtle rounding anomalies, silent data corruption, and audit traceability failures. This specification establishes clear equivalence partitions, boundary conditions, and acceptance criteria that verify whether the system delivers trustworthy financial intelligence.

### 1.2 Scope
- **In Scope:**
  - Observable inputs: Standardized bank statement JSON dictionaries conforming to [`contracts/examples/bank-statement.json`](../contracts/examples/bank-statement.json).
  - Observable outputs: Complete financial analysis envelopes conforming to [`contracts/examples/financial-analysis.json`](../contracts/examples/financial-analysis.json).
  - Functional behavior of all 6 core metrics:
    1. Total Credit (`bank.total_credit.v1`)
    2. Total Debit (`bank.total_debit.v1`)
    3. Net Cash Flow (`bank.net_cash_flow.v1`)
    4. Opening Balance (`bank.opening_balance.v1`)
    5. Closing Balance (`bank.closing_balance.v1`)
    6. Balance Reconciliation (`bank.balance_reconciliation.v1`)
  - Overall document reliability ratings (`valid`, `unreliable`, `insufficient_data`) and warning messages.
  - Source traceability arrays (`source_rows` and `field_paths`).
  - Robustness under numeric edge cases: non-negative credit/debit magnitudes, negative balances (overdrafts), multi-crore amounts, Indian and International number grouping formats, non-finite numbers (`NaN`, `Infinity`), and missing currencies.
- **Out of Scope:**
  - Internal unit test coverage of private helper functions (`_to_decimal`, `_build_source_ref`).
  - Database schema migrations and RLS policy testing (covered in [`database-schema.md`](database-schema.md)).
  - Third-party LLM response quality (covered in [`ai-and-analysis-integration-guide.md`](ai-and-analysis-integration-guide.md)).

---

## 2. Bank Statement Analytics Functionality Under Test

From an external perspective, the analytics subsystem functions as a black-box mathematical engine:

```
+---------------------------------------------------------------+
|                      OBSERVABLE INPUT                         |
|  Standardized Bank Statement (JSON Object)                    |
|  • currency: "INR" | "USD" | null                             |
|  • opening_balance: "10,000.00" | 10000 | null                |
|  • closing_balance: "12,500.00" | 12500 | null                |
|  • transactions: [ { date, description, debit, credit, ... } ]|
|  • source_metadata: { document_id, sheet_name }               |
|  • source_locations: { opening_balance, closing_balance }     |
+-------------------------------+-------------------------------+
                                |
                                v
               [ BANK STATEMENT ANALYTICS ENGINE ]
                                |
                                v
+---------------------------------------------------------------+
|                      OBSERVABLE OUTPUT                        |
|  Financial Analysis Envelope (JSON Object)                    |
|  • workspace_id: UUID | null                                  |
|  • document_type: "bank_statement"                            |
|  • currency: "INR" | null                                     |
|  • reliability: "valid" | "unreliable" | "insufficient_data"  |
|  • warnings: [ "warning string", ... ]                        |
|  • metrics: [                                                 |
|      {                                                        |
|        key: "total_credit",                                   |
|        value: 5000.0,                                         |
|        unit: "INR",                                           |
|        status: "available",                                   |
|        reason: null,                                          |
|        calculation_id: "bank.total_credit.v1",                |
|        source_refs: [ { document_id, source_rows, ... } ]     |
|      },                                                       |
|      ...                                                      |
|    ]                                                          |
+---------------------------------------------------------------+
```

### 2.1 Contract Invariants Under Test
1. **Mathematical Invariant:** $\text{Net Cash Flow} = \text{Total Credit} - \text{Total Debit}$.
2. **Reconciliation Invariant:** $\text{Discrepancy} = (\text{Opening Balance} + \text{Total Credit} - \text{Total Debit}) - \text{Closing Balance}$. Discrepancy $= 0$ is required for `reliability: "valid"`.
3. **No Silent Defaults:** Missing or invalid values must never be silently converted to `0` or default currencies.
4. **Currency Gating:** Missing statement currency blocks all monetary KPIs (`status: "unavailable"`, `unit: null`, `reason: "Missing statement currency; monetary units unconfirmed."`) and forces `reliability: "insufficient_data"`.
5. **Traceability:** Only transactions with active movements ($> 0$) contribute to `source_rows` and `field_paths`. Contributing row numbers must be positive integers ($\ge 1$).

---

## 3. Equivalence Partitioning (EP)

Equivalence partitioning divides the input domain into classes of valid and invalid inputs, where all members of a class are expected to yield equivalent observable outcomes.

| Partition ID | Input Dimension | Equivalence Class Description | Type | Expected Observable Outcome |
| :--- | :--- | :--- | :---: | :--- |
| **EP-AMT-V1** | Transaction Amount | Plain integer or decimal numeric values (e.g., `500`, `1250.75`, `0.001`) | Valid | Successfully parsed to exact numeric `Decimal`; metric available. Sub-cent/sub-paisa fractions ($\ge 3$ decimals) are accepted by calculation helper and transaction schema. |
| **EP-AMT-V2** | Transaction Amount | International 3-digit comma grouping (e.g., `"1,500.00"`, `"1,000,000.00"`) | Valid | Successfully parsed to exact numeric value; commas stripped cleanly. |
| **EP-AMT-V3** | Transaction Amount | Indian 2-digit comma grouping (e.g., `"1,50,000.00"`, `"10,00,000.50"`, `"1,00,00,000"`) | Valid | Successfully parsed to exact numeric value conforming to Indian Lakhs/Crores. |
| **EP-AMT-V4** | Transaction Amount | Zero numeric value (`0`, `0.00`, `"0.00"`) | Valid | Accepted as zero movement; excluded from contributing `source_rows` and `field_paths`. |
| **EP-BAL-V1** | Account Balance | Positive balance (e.g., `10000.00`) | Valid | Normal positive balance accepted for opening/closing balance. |
| **EP-BAL-V2** | Account Balance | Negative balance / Overdraft (e.g., `-1500.00`, `"-1,500.00"`) | Valid | Accepted for opening/closing balance; reflects overdraft account position. |
| **EP-AMT-I1** | Transaction Amount | Negative credit or debit magnitude (e.g., `credit: -50.00`) | Invalid | Rejected; metric marked `status: "unavailable"` with negative magnitude reason. |
| **EP-AMT-I2** | Transaction Amount | Malformed comma grouping (e.g., `"1,00"`, `"1,0000"`, `",100"`, `"1,500.0,0"`) | Invalid | Rejected; metric marked `status: "unavailable"` with invalid non-numeric reason. |
| **EP-AMT-I3** | Transaction Amount | Non-finite values (`"NaN"`, `"Infinity"`, `"-Infinity"`, float `nan`) | Invalid | Rejected; metric marked `status: "unavailable"` without causing system crash. |
| **EP-AMT-I4** | Transaction Amount | Boolean primitives (`true`, `false`) | Invalid | Rejected; booleans must not coerce to 1 or 0; metric marked `unavailable`. |
| **EP-AMT-I5** | Transaction Amount | Non-numeric arbitrary strings (`"N/A"`, `"pending"`, `""`) | Invalid | Rejected; metric marked `status: "unavailable"`. |
| **EP-CUR-V1** | Currency | Valid non-empty 3-letter currency code (e.g., `"INR"`, `"USD"`, `"EUR"`) | Valid | Units confirmed; metrics marked `status: "available"` with matching `unit`. |
| **EP-CUR-I1** | Currency | Missing currency (`null` or omitted key) | Invalid | All monetary metrics `unavailable` with `unit: null`; `reliability: "insufficient_data"`; warning: `"Missing statement currency; monetary units unconfirmed."`. |
| **EP-CUR-I2** | Currency | Blank or whitespace string (`""`, `"   "`) | Invalid | Evaluated as unconfirmed currency; `reliability: "insufficient_data"`. |
| **EP-CUR-I3** | Currency | Malformed non-empty currency code (e.g., `"US Dollar"`, `"123"`, `"IN"`, `"USDT"`) | Invalid | Rejected at schema-validation layer with `pydantic.ValidationError` (`validate_currency` requires 3-letter uppercase ISO code); yields HTTP 422 (`invalid_upload_fields`) at the API boundary before reaching analysis. |
| **EP-TXN-V1** | Transactions Array | Non-empty array of valid transaction dictionaries | Valid | Normal multi-transaction summation and trace generation. |
| **EP-TXN-V2** | Transactions Array | Empty array (`[]`) with matching balances ($O = C$) | Valid | Zero activity analysis: `credit=0`, `debit=0`, `net=0`, `reliability: "valid"`, `warnings: []`. |
| **EP-TXN-I1** | Transactions Array | Empty array (`[]`) with mismatching balances ($O \ne C$) | Invalid | Reconciliation discrepancy detected; `reliability: "unreliable"`. |
| **EP-TXN-I2** | Transactions Array | Empty array (`[]`) with missing $O$ or $C$ balance | Invalid | Incomplete statement; `reliability: "insufficient_data"` with balance warning. |
| **EP-TXN-I3** | Transactions Array | Missing `"transactions"` key or non-list value | Invalid | Metric marked `unavailable`; `reliability: "insufficient_data"`. |
| **EP-ROW-V1** | Source Row Index | Positive integer ($\ge 1$, e.g., `4`, `142`) | Valid | Included in `source_refs.source_rows` for auditability. |
| **EP-ROW-I1** | Source Row Index | Non-positive or non-integer (`0`, `-5`, `2.5`, `"row-4"`) | Invalid | Rejected; metric marked `unavailable` due to invalid `source_row` structure. |
| **EP-REC-V1** | Balance Reconciliation | Exact balance match: $O + C_{tot} - D_{tot} = C$ | Valid | Discrepancy $= 0$; `reliability: "valid"`; no mismatch warning. |
| **EP-REC-I1** | Balance Reconciliation | Mismatched balance: $O + C_{tot} - D_{tot} \ne C$ | Invalid | Discrepancy $\ne 0$; `reliability: "unreliable"`; mismatch warning generated. |

---

## 4. Boundary Value Analysis (BVA)

Boundary value analysis focuses on testing the extremes and edges of input partitions where financial defects frequently manifest.

| Boundary ID | Target Parameter | Boundary Value | Justification & Edge Condition | Expected Observable Result |
| :--- | :--- | :--- | :--- | :--- |
| **BVA-AMT-01** | Credit / Debit | `0.00` | Zero monetary movement boundary. | Accepted as valid zero; excluded from contributing source rows. |
| **BVA-AMT-02** | Credit / Debit | `0.001` | Smallest strictly positive sub-cent/sub-paisa quantum ($> 0.00$). Neither the transaction schema (`BankTransaction` with `ge=0`) nor `_to_decimal()` restricts inputs to 2 decimal places. | Included in summation ($> 0$ threshold met); added to `source_rows` and `field_paths`. |
| **BVA-AMT-03** | Credit / Debit | `0.01` | Conventional 2-decimal currency display resolution (1 cent / 1 paisa). Standard monetary currency display boundary. | Included in summation; added to `source_rows` and `field_paths`. |
| **BVA-AMT-04** | Credit / Debit | `-0.001` / `-0.01` | Smallest negative value (polarity boundary $< 0.00$). | Rejected: `credit`/`debit` magnitudes must be $\ge 0$. Metric `unavailable`. |
| **BVA-AMT-05** | Balance | `0.00` | Zero balance boundary. | Accepted as valid zero opening/closing balance. |
| **BVA-AMT-06** | Balance | `-0.01` | Smallest overdraft balance. | Accepted as valid negative balance for opening/closing balance. |
| **BVA-GRP-01** | Integer String | `"999"` | Maximum 3-digit ungrouped integer. | Accepted without commas. |
| **BVA-GRP-02** | Integer String | `"1,000"` | Minimum 4-digit International grouped integer. | Accepted; parsed to `1000`. |
| **BVA-GRP-03** | Integer String | `"99,999"` | Maximum 5-digit number before Lakh transition. | Accepted as valid International format (`"99,999"` has 3 trailing digits, structurally valid). |
| **BVA-GRP-04** | Integer String | `"1,00,000"` | Minimum 6-digit Indian Lakh grouping. | Accepted as valid Indian format; parsed to `100000`. |
| **BVA-GRP-05** | Integer String | `"99,99,999"` | Maximum Lakh grouping before Crore transition. | Accepted as valid Indian format; parsed to `9999999`. |
| **BVA-GRP-06** | Integer String | `"1,00,00,000"` | Minimum 8-digit Indian Crore grouping. | Accepted as valid Indian format; parsed to `10000000`. |
| **BVA-GRP-07** | Comma Placement | `"1,00.00"` | Underflow in thousand grouping (2 digits instead of 3). | Rejected: malformed grouping. Metric `unavailable`. |
| **BVA-GRP-08** | Comma Placement | `"1,0000.00"` | Overflow in grouping (4 digits). | Rejected: malformed grouping. Metric `unavailable`. |
| **BVA-ROW-01** | Source Row Index | `0` | Immediately below valid 1-based row index. | Rejected: `source_row` must be $\ge 1$. Metric `unavailable`. |
| **BVA-ROW-02** | Source Row Index | `1` | Minimal valid 1-based row index. | Accepted; recorded in `source_rows: [1]`. |
| **BVA-TXN-01** | Transactions Count | `0` (`[]`) | Empty transaction list boundary. | Handled via Empty Transactions Policy ($O = C$ valid; $O \ne C$ unreliable). |
| **BVA-TXN-02** | Transactions Count | `1` | Minimal non-empty transaction list. | Normal single transaction processing. |
| **BVA-REC-01** | Discrepancy | `0.00` | Exact reconciliation balance. | Discrepancy $= 0$; `reliability: "valid"`. |
| **BVA-REC-02** | Discrepancy | `+0.01` | Smallest positive discrepancy. | Discrepancy $= +0.01$; `reliability: "unreliable"`; warning issued. |
| **BVA-REC-03** | Discrepancy | `-0.01` | Smallest negative discrepancy. | Discrepancy $= -0.01$; `reliability: "unreliable"`; warning issued. |
| **BVA-PRC-01** | Numeric Precision | `1000000000000.50` | Large multi-trillion value with fractional paise. | Exact Decimal precision preserved; no binary float truncation. |

> **Precision Layer Architecture Note (Helper Precision vs. Schema Restrictions):**
> 1. **Calculation Helper (`_to_decimal`):** Employs arbitrary-precision Python `Decimal` arithmetic. It parses plain decimals (including fractional sub-cent amounts like `0.001` or high-precision values like `123456789012345.6789012345`) and grouped strings without enforcing a two-decimal-place limit. It defensively rejects booleans (`True`/`False`), non-finite values (`NaN`, `Infinity`), and malformed comma grouping.
> 2. **Transaction Schema (`BankTransaction`):** Imposes schema validation requiring `ge=0` (non-negative) and `allow_inf_nan=False` on `credit` and `debit` fields, but does not enforce a minimum positive quantum of `0.01` or round to two decimal places. Sub-cent values (`0.001`) are schema-valid.
> 3. **Currency & Wire Formatting:** While `0.01` represents the conventional display boundary for cents/paise in user-facing UI and reporting, `0.001` is accepted by both the parser schema and calculation engine.

---

## 5. Acceptance Test Cases for Bank Statement Calculations

The following structured test cases specify the complete acceptance requirements for the bank statement analytics engine.

### 5.1 Suite A: Credits, Debits, and Net Cash Flow

| Test Case ID | Scenario / Feature | Observable Input / Condition | Expected Observable Result | Acceptance Criterion |
| :--- | :--- | :--- | :--- | :--- |
| **TC-BB-BNK-001** | Standard Credit Summation | 3 transactions: `credit: 1500.00` (row 6), `credit: 3500.00` (row 7), `credit: 0.00` (row 8). Currency: `"INR"`. | `status: "available"`<br>`value: 5000.00`<br>`unit: "INR"`<br>`calculation_id: "bank.total_credit.v1"`<br>`source_refs: [ { source_rows: [6, 7], field_paths: ["transactions[0].credit", "transactions[1].credit"] } ]` | Sums only non-zero positive credits; ignores zero credit; records exact 1-based source rows. |
| **TC-BB-BNK-002** | Standard Debit Summation | 3 transactions: `debit: 500.00` (row 7), `debit: 2000.00` (row 8), `debit: 0.00` (row 6). Currency: `"INR"`. | `status: "available"`<br>`value: 2500.00`<br>`unit: "INR"`<br>`calculation_id: "bank.total_debit.v1"`<br>`source_refs: [ { source_rows: [7, 8], field_paths: ["transactions[1].debit", "transactions[2].debit"] } ]` | Sums non-zero debits; captures correct source rows and field paths. |
| **TC-BB-BNK-003** | Net Cash Flow Calculation | `total_credit = 5000.00`, `total_debit = 2500.00`. Contributing rows: credit `[6, 7]`, debit `[7, 8]`. | `status: "available"`<br>`value: 2500.00`<br>`unit: "INR"`<br>`calculation_id: "bank.net_cash_flow.v1"`<br>`source_refs: [ { source_rows: [6, 7, 8] } ]` | Correctly evaluates $5000 - 2500 = 2500$; merges unique source rows in sorted order (`[6, 7, 8]`). |
| **TC-BB-BNK-004** | Negative Net Cash Flow (Net Outflow) | `total_credit = 1000.00`, `total_debit = 3500.00`. Currency: `"INR"`. | `status: "available"`<br>`value: -2500.00`<br>`unit: "INR"` | Properly represents deficit cash flow with negative sign; never clamps to zero. |
| **TC-BB-BNK-005** | Rejection of Negative Credit Magnitude | Transaction at index 0 has `credit: -100.00`. | `status: "unavailable"`<br>`value: null`<br>`reason` indicates negative credit magnitude. | Credit magnitude must be non-negative; rejects negative transaction amounts. |
| **TC-BB-BNK-006** | Rejection of Negative Debit Magnitude | Transaction at index 1 has `debit: -50.25`. | `status: "unavailable"`<br>`value: null`<br>`reason` indicates negative debit magnitude. | Debit magnitude must be non-negative; rejects negative transaction amounts. |

---

### 5.2 Suite B: Opening & Closing Balances and Reconciliation

| Test Case ID | Scenario / Feature | Observable Input / Condition | Expected Observable Result | Acceptance Criterion |
| :--- | :--- | :--- | :--- | :--- |
| **TC-BB-BNK-007** | Opening Balance Extraction | `opening_balance: "10,000.00"`, `currency: "INR"`, `source_locations: { opening_balance: { source_row: 4 } }`. | `status: "available"`<br>`value: 10000.00`<br>`unit: "INR"`<br>`calculation_id: "bank.opening_balance.v1"`<br>`source_refs: [ { source_rows: [4], field_paths: ["opening_balance"] } ]` | Parses monetary string; retrieves source row from `source_locations.opening_balance`. |
| **TC-BB-BNK-008** | Closing Balance Extraction | `closing_balance: "12,500.00"`, `currency: "INR"`, `source_locations: { closing_balance: { source_row: 9 } }`. | `status: "available"`<br>`value: 12500.00`<br>`unit: "INR"`<br>`calculation_id: "bank.closing_balance.v1"`<br>`source_refs: [ { source_rows: [9], field_paths: ["closing_balance"] } ]` | Parses monetary string; retrieves source row from `source_locations.closing_balance`. |
| **TC-BB-BNK-009** | Negative Overdraft Balance | `opening_balance: "-1,500.00"`, `closing_balance: "-500.00"`. Currency: `"USD"`. | `opening_balance.value: -1500.00`<br>`closing_balance.value: -500.00`<br>`status: "available"` | Validates that account balances can be negative (overdraft accounts) unlike transaction magnitudes. |
| **TC-BB-BNK-010** | Perfect Balance Reconciliation | `opening_balance = 10000.00`, `total_credit = 5000.00`, `total_debit = 2500.00`, `closing_balance = 12500.00`. | `status: "available"`<br>`value: 0.00`<br>`reason: null`<br>`calculation_id: "bank.balance_reconciliation.v1"`<br>Overall `reliability: "valid"` | Equation $10000 + 5000 - 2500 = 12500$ balances exactly; difference is 0; reliability is valid. |
| **TC-BB-BNK-011** | Reconciliation Mismatch Detection | `opening_balance = 10000.00`, `total_credit = 5000.00`, `total_debit = 2500.00`, `closing_balance = 13000.00`. | `status: "available"`<br>`value: -500.00`<br>`reason` details mismatch (difference -500.00)<br>Overall `reliability: "unreliable"` | Discrepancy detected; document marked `unreliable`; warning generated detailing equation. |
| **TC-BB-BNK-012** | Reconciliation with Excluded Metric | Same as TC-BB-BNK-011, but called with `include_reconciliation_metric: false`. | `metrics` array contains only 3 primary KPIs (`total_credit`, `total_debit`, `net_cash_flow`).<br>Overall `reliability: "unreliable"`. | Reconciliation is evaluated for overall document reliability even when not requested in the `metrics` list. |

---

### 5.3 Suite C: Empty Transactions Policy

| Test Case ID | Scenario / Feature | Observable Input / Condition | Expected Observable Result | Acceptance Criterion |
| :--- | :--- | :--- | :--- | :--- |
| **TC-BB-BNK-013** | Zero Activity Account (Matching Balances) | `transactions: []`, `opening_balance: "5,000.00"`, `closing_balance: "5,000.00"`, `currency: "INR"`. | `reliability: "valid"`<br>`warnings: []`<br>`total_credit: 0.00`<br>`total_debit: 0.00`<br>`net_cash_flow: 0.00`<br>`reconciliation_difference: 0.00` | Zero-activity account accepted as valid; no artificial warnings generated; metrics equal zero. |
| **TC-BB-BNK-014** | Empty Transactions with Balance Mismatch | `transactions: []`, `opening_balance: "5,000.00"`, `closing_balance: "6,000.00"`, `currency: "INR"`. | `reliability: "unreliable"`<br>`warnings` contains mismatch notice.<br>`reconciliation_difference: -1000.00` | Account balance changed without recorded transactions; marked `unreliable`. |
| **TC-BB-BNK-015** | Empty Transactions with Missing Opening Balance | `transactions: []`, `opening_balance: null`, `closing_balance: 5000.00`, `currency: "INR"`. | `reliability: "insufficient_data"`<br>`warnings` contains missing balance notice. | Missing balance prevents confirmation of zero activity; marked `insufficient_data`. |
| **TC-BB-BNK-016** | Empty Transactions with Missing Closing Balance | `transactions: []`, `opening_balance: 5000.00`, `closing_balance: null`, `currency: "INR"`. | `reliability: "insufficient_data"`<br>`warnings` contains missing balance notice. | Missing balance prevents confirmation of zero activity; marked `insufficient_data`. |
| **TC-BB-BNK-017** | Omitted Transactions Key | Statement dictionary has no `"transactions"` key. | `status: "unavailable"`<br>`reliability: "insufficient_data"`<br>`warnings` notes missing required transactions. | Never silently fabricates an empty transaction list when key is absent. |

---

### 5.4 Suite D: Missing Currency Policy

| Test Case ID | Scenario / Feature | Observable Input / Condition | Expected Observable Result | Acceptance Criterion |
| :--- | :--- | :--- | :--- | :--- |
| **TC-BB-BNK-018** | Missing Currency on Statement | Statement has `currency: null`. Valid transactions and balances present. | All monetary metrics have:<br>• `status: "unavailable"`<br>• `value: null`<br>• `unit: null`<br>• `reason: "Missing statement currency; monetary units unconfirmed."`<br>Overall `reliability: "insufficient_data"`<br>Overall `currency: null`<br>`warnings: ["Missing statement currency; monetary units unconfirmed."]` | Enforces contract rule: unknown currency blocks all monetary KPIs; exact warning text emitted. |
| **TC-BB-BNK-019** | Source Reference Preservation on Missing Currency | Statement has `currency: null`, but valid transaction credit on row 6 and debit on row 7. | `total_credit.source_refs: [ { source_rows: [6], field_paths: ["transactions[0].credit"] } ]`<br>`total_debit.source_refs: [ { source_rows: [7], field_paths: ["transactions[1].debit"] } ]` | Source references are strictly preserved even when metric is unavailable due to missing currency. |
| **TC-BB-BNK-020** | Empty or Whitespace Currency String | Statement has `currency: ""` or `currency: "   "`. | Evaluated identically to `null` currency.<br>`reliability: "insufficient_data"`<br>`warning: "Missing statement currency; monetary units unconfirmed."` | Blank or whitespace strings do not pass as valid currency codes. |
| **TC-BB-BNK-021** | Non-String Currency Value | Statement has `currency: 123` or `currency: ["INR"]`. | Evaluated identically to missing currency.<br>All monetary metrics unavailable. | Rejects non-string currency types without crashing. |

---

### 5.5 Suite E: Number Formats, Comma Groupings, and Non-Finites

| Test Case ID | Scenario / Feature | Observable Input / Condition | Expected Observable Result | Acceptance Criterion |
| :--- | :--- | :--- | :--- | :--- |
| **TC-BB-BNK-022** | Valid International Grouping | Transaction credit: `"1,500.00"`, `"1,000,000.00"`, `"123,456,789.25"`. | All values parsed accurately to `1500.00`, `1000000.00`, `123456789.25`. Metric `status: "available"`. | Correctly parses standard 3-digit international comma groupings. |
| **TC-BB-BNK-023** | Valid Indian Number Grouping | Transaction credit: `"1,50,000.00"` (1.5 Lakhs), `"10,00,000.50"` (10 Lakhs), `"1,00,00,000"` (1 Crore). | All values parsed accurately to `150000.00`, `1000000.50`, `10000000.00`. Metric `status: "available"`. | Correctly parses Indian numbering system (Lakhs & Crores) with 2-digit higher groupings. |
| **TC-BB-BNK-024** | Negative Grouped Balances | Opening balance: `"-1,50,000.00"`, Closing balance: `"-10,00,000.50"`. | Parsed accurately to `-150000.00` and `-1000000.50`. Metric `status: "available"`. | Supports negative signs preceding grouped Indian/International strings. |
| **TC-BB-BNK-025** | Malformed Comma Grouping Rejection | Transaction credit contains malformed groupings:<br>`"1,00"`, `"1,0000"`, `",100"`, `"100,"`, `"1,2,3"`, `"1,500.0,0"`. | `status: "unavailable"`<br>`value: null`<br>`reason` indicates non-numeric/malformed value. | Rejects irregular groupings; does not blindly strip commas without syntax validation. |
| **TC-BB-BNK-026** | Non-Finite Value Rejection: NaN | Transaction credit or balance is `"NaN"`, `"nan"`, or float `nan`. | `status: "unavailable"`<br>`value: null`<br>`reason` indicates non-numeric credit. | Strictly rejects Not-a-Number inputs; never propagates `NaN` into financial results. |
| **TC-BB-BNK-027** | Non-Finite Value Rejection: Infinity | Transaction credit or balance is `"Infinity"`, `"-inf"`, or float `inf`. | `status: "unavailable"`<br>`value: null`<br>`reason` indicates non-numeric credit. | Strictly rejects Infinite inputs; prevents numeric overflow. |
| **TC-BB-BNK-028** | Boolean Coercion Rejection | Transaction credit is `true` or `false`. | `status: "unavailable"`<br>`value: null`<br>`reason` indicates invalid credit type. | Rejects boolean types; prevents Python `bool` from coercing to `1` or `0`. |
| **TC-BB-BNK-029** | Large Value Precision Preservation | Transaction credit: `"98,765,432,109.87"`. | Exact Decimal value `98765432109.87` preserved.<br>Serialization maintains numeric representation. | No precision loss occurs for large multi-billion/crore values. |

---

### 5.6 Suite F: Source References, Traceability, and Edge Cases

| Test Case ID | Scenario / Feature | Observable Input / Condition | Expected Observable Result | Acceptance Criterion |
| :--- | :--- | :--- | :--- | :--- |
| **TC-BB-BNK-030** | Zero Source Row Validation | Transaction has `source_row: 0`. | `status: "unavailable"`<br>`value: null`<br>`reason` specifies `source_row` must be positive integer $\ge 1$. | Enforces 1-based index invariant; rejects row 0. |
| **TC-BB-BNK-031** | Negative Source Row Validation | Transaction has `source_row: -4`. | `status: "unavailable"`<br>`value: null`<br>`reason` specifies `source_row` must be positive integer $\ge 1$. | Rejects negative row index. |
| **TC-BB-BNK-032** | Source Locations Missing on Statement | Statement has no `source_locations` key. Opening balance and closing balance are valid. | `status: "available"`<br>`opening_balance.source_refs: [ { source_rows: [], field_paths: ["opening_balance"] } ]` | Gracefully handles absent `source_locations`; returns empty `source_rows` without error. |
| **TC-BB-BNK-033** | Malformed Source Locations Structure | `source_locations` is a string `"invalid"` or integer `123`. | `status: "unavailable"`<br>`reason` indicates `source_locations` must be a dictionary. | Rejects invalid container type for `source_locations`. |
| **TC-BB-BNK-034** | Contract Fixture Exact Equivalence | Complete [`contracts/examples/bank-statement.json`](../contracts/examples/bank-statement.json) input with workspace ID `"20000000-0000-4000-8000-000000000001"`. | Exact dictionary equivalence with [`contracts/examples/financial-analysis.json`](../contracts/examples/financial-analysis.json). | Guarantees complete fidelity to the agreed team interface contract. |
| **TC-BB-BNK-035** | REST `/analysis` Wire Response Precision | High-precision monetary transaction (e.g., `123456789012345.6789012345`) queried via `GET /api/workspaces/{id}/analysis`. Response parsed via Python `json.loads(response.content, parse_float=Decimal)`. | Exact Decimal equality: `metric["value"] == Decimal("123456789012345.6789012345")`. Integers serialized without decimals (e.g., `5000`); fractional numbers preserve all significant places without IEEE 754 float truncation. | Guarantees exact financial precision over HTTP wire delivery without losing paise/cents. |

#### Detailed Specification for TC-BB-BNK-035: REST Serialization Precision Verification

- **Target Endpoint:** `GET /api/workspaces/{id}/analysis`
- **Existing Test Reference:** [`backend/tests/api/test_workspace_analysis.py`](../backend/tests/api/test_workspace_analysis.py) (`test_bank_analysis_keeps_real_ids_and_exact_json_values`).
- **Precision Hazard (Why Ordinary Float Parsing is Insufficient):**
  Standard IEEE 754 double-precision 64-bit binary floats provide only 53 bits of significand (mantissa), translating to approximately 15 to 17 decimal digits of precision. When monetary amounts contain large numbers with extended fractional paise/cents (such as `Decimal("123456789012345.6789012345")`, which has 25 significant digits), standard JSON decoders (such as default Python `json.loads(response.content)` without parameters, or browser `JSON.parse()`) convert JSON number literals into binary floats, discarding digits beyond the 17th significant figure and introducing rounding errors.
- **Backend Wire Serialization:**
  In [`backend/app/schemas/analysis_responses.py`](../backend/app/schemas/analysis_responses.py), `WorkspaceAnalysisResponse.to_wire_json()` uses `simplejson.dumps(self.model_dump(mode="python"), use_decimal=True, allow_nan=False, default=str)`. This emits exact, unrounded decimal number tokens (not strings) onto the wire.
- **Client Verification Protocol:**
  To verify exact precision, black-box client test harnesses must decode the HTTP response body using Python's `parse_float=Decimal`:
  ```python
  import json
  from decimal import Decimal
  import httpx

  response = httpx.get(
      f"http://localhost:8000/api/workspaces/{workspace_id}/analysis",
      headers={"Authorization": f"Bearer {access_token}"},
  )
  assert response.status_code == 200

  # Decode numbers directly into Python Decimal to prevent binary float truncation
  payload = json.loads(response.content, parse_float=Decimal)
  metric = next(m for m in payload["metrics"] if m["key"] == "total_credit")

  # Exact Decimal comparison against expected value
  expected_amount = Decimal("123456789012345.6789012345")
  assert metric["value"] == expected_amount
  ```
- **Execution Status Note:**
  While the automated API test `test_bank_analysis_keeps_real_ids_and_exact_json_values` passes in the internal repository test suite, this system acceptance case represents the black-box client verification standard and is marked **Pending Live Execution** until run against a live deployed server.

---

## 6. Distinction Between Proposed Acceptance Tests and Existing Automated Tests

It is critical to distinguish between the **existing automated test suite** already executing in the repository and the **proposed black-box acceptance test suite** specified in this document:

```
               +---------------------------------------------+
               |        PROPOSED ACCEPTANCE TESTS            |
               |  (System-Level Black-Box Verification)      |
               |  • Specified in this document (35 cases)    |
               |  • Run against HTTP API & CLI endpoints     |
               |  • Zero internal white-box mocks            |
               +----------------------+----------------------+
                                      |
                                      v
               +---------------------------------------------+
               |        EXISTING AUTOMATED TESTS             |
               |  (Unit & API Integration Test Suite)        |
               |  • backend/tests/analysis/test_bank_kpis.py |
               |  • backend/tests/api/test_workspace_analysis.py
               |  • Direct function & mocked HTTP assertions |
               +---------------------------------------------+
```

### 6.1 Status of Existing Automated Tests
The repository currently executes two distinct tiers of automated tests:
1. **Unit & Calculation Tests:**
   - **Location:** [`backend/tests/analysis/test_bank_kpis.py`](../backend/tests/analysis/test_bank_kpis.py)
   - **Execution Evidence:** 119 passed tests (Pytest 8.4.2 on Python 3.11.9).
   - **Scope:** Unit-level verification of `bank_kpis.py` functions, regex pattern matching, Decimal arithmetic, and exact matching against the fixture `contracts/examples/financial-analysis.json`.
   - **Nature:** White-box and module-level unit tests executed directly in the Python runtime.
2. **Automated API Integration Tests:**
   - **Location:** [`backend/tests/api/test_workspace_analysis.py`](../backend/tests/api/test_workspace_analysis.py)
   - **Scope:** FastAPI route handling over mocked Supabase HTTP transport (`analysis_client` fixture):
     - **Exact Wire Serialization Precision:** `test_bank_analysis_keeps_real_ids_and_exact_json_values` verifies that 25-digit `Decimal("123456789012345.6789012345")` preserves exact JSON number literals and is decoded via `parse_float=Decimal`.
     - **Unauthenticated Rejection (HTTP 401):** `test_authentication_and_uuid_validation_precede_database_reads` asserts that requests lacking valid Bearer tokens return HTTP 401 with `WWW-Authenticate: Bearer` before any database reads occur.
     - **Cross-Tenant / Foreign Workspace Isolation (HTTP 404):** `test_missing_or_foreign_workspace_does_not_read_document` asserts that querying another user's workspace or nonexistent workspace returns HTTP 404 without leaking document contents.
     - **Document Not Ready (HTTP 409):** `test_document_not_ready` asserts that workspaces with document status `uploaded` or `failed` return HTTP 409 with error code `document_not_ready`.
     - **Missing Currency Policy:** `test_bank_analysis_with_missing_currency_reports_unavailable_metrics` verifies that unconfirmed currency yields `reliability: "insufficient_data"` and `unit: "unknown"`.

### 6.2 Nature of Proposed Black-Box Acceptance Tests
- **Status:** **Proposed / Specification Plan.** None of the 35 proposed black-box test cases in Section 5 are claimed to have been executed as end-to-end black-box system tests.
- **Scope:** Intended for execution by independent QA engineers or automated HTTP test harnesses (e.g., Postman, Newman, Playwright, or black-box curl scripts) calling external REST endpoints (`POST /api/upload`, `GET /api/workspaces/{id}/analysis`).
- **Key Differences:**
  1. **Black-box execution:** No imports of Python modules or helper functions. Test inputs are supplied as serialized JSON files or multipart CSV/XLSX uploads.
  2. **End-to-End Environment:** Tests the complete network, auth, serialization, and response pipeline against a live, running server without mocked database transports.
  3. **Consumer Independence:** Validates that downstream consumers (Frontend, AI Assistant) receive the exact expected contract format without assumptions about backend internals.

---

## 7. Observable Acceptance Verification Guide

Acceptance can be validated purely through observable inputs and outputs without access to source code or internal debugger hooks.

### 7.1 Verification Methodology via REST API

The complete upload-to-analysis workflow must be executed from the `backend/` directory (`cd backend`), targeting a running FastAPI server instance (e.g., `http://localhost:8000`).

#### Step 1: Authentication & Token Retrieval
All workspace endpoints require authentication via Supabase GoTrue Bearer JWT. Unauthenticated requests are rejected with HTTP 401 before any database reads take place (verified by `test_authentication_and_uuid_validation_precede_database_reads` in `backend/tests/api/test_workspace_analysis.py`).
```bash
# Set active Supabase Bearer token
export ACCESS_TOKEN="<supabase_bearer_jwt>"
```

#### Step 2: Ingest Test Statement via Upload API (`POST /api/upload`)
The intake endpoint [`backend/app/api/routes/upload.py`](../backend/app/api/routes/upload.py) accepts multipart form uploads for both CSV (`.csv`) and Excel (`.xlsx`) files (validated via `validate_file_metadata` in `backend/app/services/upload_validation.py`).

Submit the standard repository fixture [`backend/tests/parsers/fixtures/synthetic_bank_statement.csv`](../backend/tests/parsers/fixtures/synthetic_bank_statement.csv) from the `backend/` directory:
```bash
cd backend

# Upload synthetic bank statement CSV fixture (CSV and XLSX are both supported)
UPLOAD_RESPONSE=$(curl -s -S -X POST "http://localhost:8000/api/upload" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "user_type=personal" \
  -F "document_type=bank_statement" \
  -F "file=@tests/parsers/fixtures/synthetic_bank_statement.csv;type=text/csv")
```

*Observable Response Structure (`UploadResponse`):*
```json
{
  "workspace": {
    "id": "e8d7c92b-8141-4b72-8820-21a4f001c2ab",
    "name": "Synthetic Demo Bank",
    "user_type": "personal",
    "document_type": "bank_statement",
    "created_at": "2026-11-24T10:00:00Z"
  },
  "document": {
    "id": "d1a58712-9c3f-4e8b-b1e2-3a4b5c6d7e8f",
    "status": "parsed"
  }
}
```
*Observable Assertion:* Response status must be `201 Created`. Extract the generated `WORKSPACE_ID` directly from the `workspace.id` field:
```bash
# Extract WORKSPACE_ID from response
WORKSPACE_ID=$(echo "$UPLOAD_RESPONSE" | jq -r '.workspace.id')
echo "Target Workspace ID: $WORKSPACE_ID"
```

#### Step 3: Verify Observable Financial Analysis Envelope (`GET /api/workspaces/{id}/analysis`)

Target the registered REST route [`backend/app/api/routes/workspaces.py`](../backend/app/api/routes/workspaces.py) using the extracted `WORKSPACE_ID`:
```bash
curl -s -S -X GET "http://localhost:8000/api/workspaces/$WORKSPACE_ID/analysis" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

> **Endpoint Registration Status:**
> `GET /api/workspaces/{id}/analysis` is formally registered on `origin/main` in [`backend/app/api/routes/workspaces.py`](../backend/app/api/routes/workspaces.py). It is backed by [`backend/app/services/workspace_analysis.py`](../backend/app/services/workspace_analysis.py) (`build_workspace_analysis()`), which verifies document readiness, calls `analyze_bank_statement()`, validates the result against `WorkspaceAnalysisResponse`, and serializes the exact decimal numbers via `to_wire_json()`.

*What to Inspect in the Response:*
1. **Top-Level Envelope Properties:**
   - `workspace_id`: Matches `$WORKSPACE_ID`.
   - `document_type`: Equals `"bank_statement"`.
   - `currency`: Equals `"INR"`.
   - `reliability`: Equals `"valid"` (reconciliation discrepancy is zero, currency is confirmed, no parsing defects).
   - `warnings`: Empty array (`[]`).
   - `metrics`: Array of metric objects.
2. **Deterministic Metric Assertions & Exact Source Rows:**
   For [`tests/parsers/fixtures/synthetic_bank_statement.csv`](../backend/tests/parsers/fixtures/synthetic_bank_statement.csv), verify each metric's `calculation_id`, `value`, `unit`, `status`, and exact 1-based `source_rows`:

   | Metric Key | Expected Value | Unit | Status | Expected Calculation ID | Exact Source Rows | Source Row Derivation in Fixture |
   | :--- | :---: | :---: | :---: | :--- | :---: | :--- |
   | `opening_balance` | `10000` | `INR` | `available` | `bank.opening_balance.v1` | `[4]` | Line 4: `Opening Balance: 10000` |
   | `total_credit` | `5000` | `INR` | `available` | `bank.total_credit.v1` | `[6]` | Line 6: `2026-01-05,Synthetic salary,0,5000,15000` |
   | `total_debit` | `2500` | `INR` | `available` | `bank.total_debit.v1` | `[7, 8]` | Line 7: `Synthetic rent,2000,0` + Line 8: `Synthetic groceries,500,0` |
   | `net_cash_flow` | `2500` | `INR` | `available` | `bank.net_cash_flow.v1` | `[6, 7, 8]` | Union of credit (`[6]`) and debit (`[7, 8]`) source rows |
   | `closing_balance` | `12500` | `INR` | `available` | `bank.closing_balance.v1` | `[9]` | Line 9: `Closing Balance: 12500` |
   | `balance_reconciliation` | `0` (or `0.00`) | `INR` | `available` | `bank.reconciliation.v1` | `[4, 6, 7, 8, 9]` | Complete audit trail ($10000 + 5000 - 2500 - 12500 = 0.00$) |

   *(Note: Line 10 in the fixture is an unmapped item: `Unrecognized export note,Synthetic note only`, which is retained in `unmapped` at row 10 and does not alter the calculation source rows).*

3. **Security and Error Response Assertions:**
   Black-box tests must also verify non-200 HTTP response codes matching the automated tests in [`backend/tests/api/test_workspace_analysis.py`](../backend/tests/api/test_workspace_analysis.py):
   - **HTTP 401 Unauthorized:** Missing or invalid `Authorization` header returns 401 with `WWW-Authenticate: Bearer` (`test_authentication_and_uuid_validation_precede_database_reads`).
   - **HTTP 404 Not Found:** Querying a workspace owned by another user or an unmapped UUID returns 404 (`test_missing_or_foreign_workspace_does_not_read_document`).
   - **HTTP 409 Conflict (`document_not_ready`):** Querying a workspace where the document is still in `uploaded` status or has `failed` status returns 409 with `detail.code == "document_not_ready"` (`test_document_not_ready`).

### 7.2 Verification via Standalone JSON Contract Runner
For offline or CI verification without running a live server, an observable contract test script passes a JSON fixture directly into the public calculation engine and checks standard exit codes and JSON output.

**Execution Directory & Path Rules:**
- The command **must be run explicitly from the `backend/` directory** (`cd backend`). This ensures Python adds `backend/` to `sys.path`, resolving `from app.analysis.bank_kpis import analyze_bank_statement`.
- Contract fixture file paths **must be relative to the `backend/` directory**, e.g., `../contracts/examples/bank-statement.json` and `../contracts/examples/financial-analysis.json`.

```bash
# Step 1: Change to backend directory
cd backend

# Step 2: Execute observable contract validation command
python -c "
import json
from app.analysis.bank_kpis import analyze_bank_statement

with open('../contracts/examples/bank-statement.json') as f:
    input_data = json.load(f)
with open('../contracts/examples/financial-analysis.json') as f:
    expected_output = json.load(f)

actual_output = analyze_bank_statement(
    input_data, workspace_id='20000000-0000-4000-8000-000000000001'
)
assert actual_output == expected_output, 'Contract mismatch detected!'
print('Observable Acceptance Verification: 100% Contract Match!')
"
```

*Observable Assertion:* The exit code must be `0`, and the printed output must confirm:
```text
Observable Acceptance Verification: 100% Contract Match!
```

---

## 8. Summary of Quality Verification

| Quality Dimension | Standard Met | Verification Details |
| :--- | :---: | :--- |
| **Traceability** | **YES** | Every positive movement maintains 1-based source row linkage to the original file. |
| **Financial Precision** | **YES** | Exact Python `Decimal` arithmetic eliminates IEEE 754 floating-point inaccuracies. |
| **Robust Parsing** | **YES** | Validated regexes support both International and Indian Lakh/Crore grouping syntax. |
| **Defensive Safety** | **YES** | Zero-tolerance policy prevents fabricated zeros, synthetic currencies, or booleans. |
| **Contract Alignment**| **YES** | 100% dictionary match with official team contract fixtures. |
