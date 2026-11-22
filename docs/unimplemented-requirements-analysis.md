# FinGenie: Unimplemented & Deferred Requirements Analysis

**Course / Context:** IT314 — Software Engineering (Group 18)  
**Track:** AI + Analysis Track  
**Contributors:** Aarushi Shah (Balance Sheet Analytics), Prince Patel (AI Conversational Assistant), Rashi Patel (Bank Analytics), Srujan (Numeric Verification Guard)  
**Target Milestone:** v1.0 Architectural Baseline & v2.0 Future Roadmap  
**Document Status:** Approved Analytical Baseline  
**Related Requirements:** FR-02, FR-03, FR-04, FR-11, FR-12, FR-13, FR-20, FR-23, FR-26; NFR-01, NFR-04, NFR-08, NFR-11, NFR-13, NFR-19  

---

## 1. Executive Summary & Problem Formulation

In modern software engineering, one of the most critical determinants of system quality and architectural integrity is the disciplined management of project scope. Requirements engineering is not merely an exercise in accumulating stakeholder desires; it is fundamentally a systematic process of trade-off evaluation, feasibility analysis, risk mitigation, and boundary enforcement. 

During the requirements elicitation phase for **FinGenie**—conducted via an 80-respondent empirical survey across retail consumers and commercial accounting stakeholders—several high-interest, ambitious capabilities were proposed. Prominent among these were:
1. **Multi-Year Predictive Financial Forecasting** (long-term machine-learning-driven balance and revenue projections),
2. **Automated Tax Optimization & Statutory Filing Advisory** (algorithmic tax minimization under Indian Direct and Indirect tax regimes),
3. **Optical Character Recognition (OCR) & Scanned Image/PDF Processing** (ingesting mobile camera photographs and scanned paper statements), and
4. **Autonomous Account Aggregator (AA) & Open Banking Live Sync** (real-time programmatic API bank scraping).

While these capabilities represent compelling marketing propositions, the AI + Analysis engineering team conducted rigorous domain analysis and formal software trade-off studies. The analysis revealed that incorporating these capabilities into the **v1.0 Minimum Viable Product (MVP)** would violate core software engineering principles, compromise mathematical accuracy, introduce severe statutory and legal liabilities, degrade system performance, and shatter FinGenie's foundational architectural promise: **100% deterministic arithmetic grounded in verifiable 1-based source-row provenance**.

Consequently, these features were deliberately **scoped out and deferred to v2.0**. This document provides an exhaustive, academic analysis of the engineering, mathematical, legal, and operational reasons governing their deferral, establishes the formal boundary conditions required for their future realization, and presents a structured conceptual framework for viva evaluation.

---

## 2. Empirical Grounding & Stakeholder Context

The prioritization decisions in FinGenie are directly grounded in empirical findings gathered from the 80-respondent financial document analysis survey.

### 2.1 The Stakeholder Demographics
- **The Retail Majority (86.3% / 69 Respondents):** Comprising salaried employees (60.0%), students (23.8%), and general consumers (2.5%). Their primary needs are simple monthly cash-flow clarity, expense categorization, tracking UPI transactions, and avoiding financial stress.
- **The Commercial Minority (13.8% / 11 Respondents):** Comprising small business owners (5.0%), accounting and finance professionals (5.0%), and freelancers (3.8%). They require liquidity indicators (Current Ratio, Working Capital), double-entry balance sheet reconciliation, and operational burn tracking.

### 2.2 Survey Divergence & The High-Demand Paradox
When surveyed on prospective features, **85.0% of respondents** expressed a strong desire for future balance estimation and financial forecasting (37.5% marked it as an absolute "Must-Have", and 47.5% as "Nice-to-Have"). Concurrently, a substantial portion of users expressed a desire for paper statement scanning (OCR) and automated tax advice.

However, cross-tabulation against non-functional priorities revealed a profound contradiction:
- **86.3% of users exhibited deep privacy apprehension** regarding uploading raw statements to external servers or cloud AI models (15.0% outright refused uploads, 11.3% were hesitant, and 60.0% demanded strict, verified privacy protections).
- **47.5% demanded near-instant processing** (26.3% demanding sub-5 second responses; 21.3% accepting up to 15 seconds).
- **100% of commercial users demanded absolute mathematical precision**, stating that any software showing unverified or hallucinated financial figures is completely unusable for business or compliance.

Building features like cloud-based multi-year forecasting or deep-learning OCR in v1.0 would directly collide with users' latency and privacy constraints while risking catastrophic calculation errors. Engineering discipline mandated deferring these high-risk features to protect the core integrity of the platform.

---

## 3. Deep-Dive Analysis of Core Deferred Features

```
+----------------------------------------------------------------------------------------------------+
|                                    FINGENIE SCOPE TAXONOMY                                         |
+----------------------------------------------------+-----------------------------------------------+
|                 v1.0 (CORE MVP)                    |               v2.0 (DEFERRED SCOPE)           |
|            Deterministic & Auditable               |            Complex, Statistical, Regulated    |
+----------------------------------------------------+-----------------------------------------------+
| • Structured Ingestion (CSV / XLSX)                | • Unstructured OCR & Scanned Vision Pipeline  |
| • Exact Arithmetic (Python Decimal, 28-pt)         | • Multi-Year Predictive AI/ML Forecasting     |
| • 1-Based Source-Row Traceability (#row-142)       | • Automated Tax Planning & Statutory Advisory |
| • Zero-Math LLM Architecture with Number Guard     | • Cross-Bank Account Aggregator (AA) Sync     |
| • Data Sufficiency Gating (>= 90 Days for Runway)  | • Unsupervised Black-Box Spend Clustering     |
+----------------------------------------------------+-----------------------------------------------+
```

### 3.1 Deferred Feature 1: Multi-Year Predictive Financial Forecasting

#### 3.1.1 Feature Description
The capability to predict an individual's or enterprise's future account balances, cash positions, revenues, and insolvency dates across multi-year forward horizons (e.g., 1 to 5 years forward) using time-series extrapolation or autoregressive generative AI models.

#### 3.1.2 Engineering & Mathematical Reasons for Deferral

1. **The "Snapshot vs. Flow" Fallacy:**  
   In accounting theory, a balance sheet represents a static, point-in-time snapshot of financial position at a single calendar instant (e.g., midnight on March 31). It contains zero time-series velocity or longitudinal rate-of-change data. Attempting to project multi-year future cash flow or solvency trajectories from an isolated single-period balance sheet is methodologically invalid. Without multi-period operational cash-flow statements or longitudinal transaction logs, any generated curve is a mathematical fiction.

2. **Data Sufficiency Gating & Longitudinal Scarcity:**  
   Under functional requirement **FR-13**, FinGenie strictly dictates that financial projections must be gated behind verifiable historical depth:
   $$\text{Historical Data Depth} \ge 90\text{ days (3 continuous months of bank transactions)}$$
   $$\text{OR}$$
   $$\text{Consecutive Audited Comparative Periods} \ge 2\text{ fiscal years}$$
   In v1.0, user onboarding primarily involves uploading a single recent monthly bank statement (30 days) or a single fiscal year balance sheet. Attempting multi-year forecasting on 30 days of data violates basic statistical sampling criteria, resulting in wild over-fitting where a one-off festival purchase or annual insurance premium is mistakenly modeled as a recurring monthly expenditure.

3. **Compounding Epistemic Uncertainty & Non-Linear Shocks ($O(t^2)$ Variance Explosion):**  
   Financial markets, business revenues, and personal cash flows are subject to non-stationary stochastic processes. Multi-year forecasting requires modeling complex exogenous variables:
   - Macroeconomic fluctuations (RBI repo rate revisions, retail inflation spikes),
   - Statutory policy changes (Union Budget income tax slab restructuring),
   - Business cycle disruptions (supply chain chokepoints, customer counterparty default).  
   Without an extensive multi-variable econometric engine, naive statistical or machine-learning extrapolations compound uncertainty quadratically ($O(t^2)$) over forward time horizons. Presenting a 3-year projection with $\pm 80\%$ confidence intervals to non-finance users gives a dangerous illusion of certainty (false solvency confidence).

4. **Preservation of the Deterministic Zero-Math AI Contract:**  
   FinGenie's core architectural principle (**NFR-11**, **NFR-13**) mandates that no Generative AI component may calculate or hallucinate financial figures. Multi-year neural forecasting models (e.g., LSTM, Transformer-based regressors) function as probabilistic "black boxes." They cannot provide exact, step-by-step mathematical proofs or tie back to exact line items in source files, violating the platform's auditable provenance standard.

#### 3.1.3 Boundary Conditions for v2.0 Implementation
- Ingestion of at least 12 to 24 continuous months of verified transaction data via the Account Aggregator framework.
- Deconstruction of expenses into strict autoregressive components: fixed baseline commitments (rent, EMIs, insurance) vs. discretionary variable spending.
- Non-deterministic projections presented exclusively as probabilistic confidence envelopes (Conservative $-1\sigma$, Expected, and Optimistic $+1\sigma$ bounds) accompanied by mandatory risk disclaimers.

---

### 3.2 Deferred Feature 2: Automated Tax Optimization & Statutory Advisory

#### 3.2.1 Feature Description
Algorithmic computation of individual or corporate tax liabilities, automated recommendations for tax-saving investments (e.g., Section 80C, 80D under the Indian Income Tax Act, 1961), automated selection between the Old and New Tax Regimes, and calculation of Input Tax Credit (ITC) for Goods and Services Tax (GST).

#### 3.2.2 Engineering, Legal & Operational Reasons for Deferral

1. **Statutory Non-Compliance and Professional Malpractice Liability:**  
   Under Indian law and international financial regulations, offering specific tax computation, tax optimization advice, or statutory tax filing recommendations without certification by the Institute of Chartered Accountants of India (ICAI) or registration as a Registered Investment Advisor (RIA) under SEBI exposes the software provider to severe civil and criminal liability. An automated recommendation that erroneously claims an ineligible deduction (e.g., claiming personal dining expenses as business deductions) could expose users to tax evasion penalties, audits, and interest under Section 234 of the Income Tax Act.

2. **Severe Information Asymmetry in Bank Narrations:**  
   Bank statements record payment **settlements**, not legal **invoices**. A bank narration typically reads:
   `UPI/23940293021/PAYTMQR/Groceries/0203` or `NEFT-N102930192-SHREE_TRADERS-MUMBAI`  
   This raw transaction string lacks the essential legal and fiscal metadata required for tax determination:
   - Was the ₹25,000 transfer a capital expenditure (capex), an operational business expense (opex), a loan repayment, or a personal gift?
   - What was the applicable GST slab (0%, 5%, 12%, 18%, or 28%)?
   - Did the recipient issue a valid GST tax invoice with an active GSTIN?  
   Attempting to infer tax deductions or compute GST returns from bank transaction strings alone is technically impossible without guessing, directly violating FinGenie's data-integrity mandate (**NFR-23**).

3. **High Policy Volatility and Regime Duality:**  
   The Indian taxation framework is subject to high statutory volatility. The co-existence of two divergent systems—the **Old Tax Regime** (replete with dozens of itemized exemptions: HRA, LTA, 80C, 80D, 24(b)) and the **New Tax Regime** (featuring concessional slabs but zero personal exemptions, with complex Section 87A marginal relief rules)—means that an optimization algorithm would require maintaining a massive, constantly shifting statutory rule engine. Hardcoding such tax logic in v1.0 would incur immense architectural coupling and maintenance overhead (**NFR-19**).

4. **Clear Requirement Demarcation in Project Baseline:**  
   Functional requirement **FR-20** explicitly establishes an immutable boundary:
   > *"The system shall display a disclaimer that AI-generated insights are informational and not investment or financial advice."*  
   Automated tax planning inherently violates this boundary. In v1.0, FinGenie positions itself strictly as an **analytical ledger and financial health diagnostic tool**, explicitly disclaiming tax advisory status.

#### 3.2.3 Boundary Conditions for v2.0 Implementation
- Direct integration with the Government of India's **GSTN (Goods and Services Tax Network)** and Income Tax e-filing APIs to ingest official XML/JSON tax forms and verified 2A/2B reconciliations.
- Implementation of a "Human-in-the-Loop" (HITL) Chartered Accountant review workflow, where FinGenie prepares pre-computed ledger aggregates, but final tax filing and deduction claims require explicit review and digital sign-off by a certified tax professional.

---

### 3.3 Deferred Feature 3: Optical Character Recognition (OCR) & Scanned Document Parsing

#### 3.3.1 Feature Description
The automated ingestion, computer vision extraction, and tabular digitization of physical paper bank statements, printed passbooks, and photograph scans (JPEG, PNG, scanned raster PDFs) into structured transaction records.

#### 3.3.2 Engineering, Security & Algorithmic Reasons for Deferral

1. **Catastrophic Arithmetic Cascades Caused by Single-Digit OCR Errors:**  
   In standard computer vision and natural language processing tasks, an OCR character error rate (CER) of 1% to 2% is considered state-of-the-art. In financial accounting, however, **a 1% error rate is catastrophic**.  
   Consider the following real-world failure modes:
   - A stray speck of dust or poor scan contrast causes OCR to misread an `'8'` as a `'0'`, turning a `₹80,000.00` debit into `₹00,000.00`.
   - A faintly printed decimal point is missed, converting `₹1,500.50` into `₹1,50,050.00`.
   - Parenthetical debit notations `(₹4,500.00)` are parsed as positive credits due to missed brackets.  
   Any single-digit or sign error instantly invalidates the fundamental bank balance reconciliation equation:
   $$\text{Opening Balance} + \sum \text{Credits} - \sum \text{Debits} = \text{Closing Balance}$$
   When this equation fails, the platform cannot verify whether the statement was tampered with, corrupted, or misparsed, triggering severe system-wide validation failures (**NFR-09**).

2. **Destruction of 100% Deterministic Source-Row Provenance:**  
   FinGenie's core differentiator and architectural integrity pillar is strict, 1-based source traceability (**FR-09**). In a digital CSV or XLSX file, row 142 is unambiguously line 142. If a user clicks on an anomalous debit card charge on the dashboard, the transaction detail drawer cites:
   $$\text{Document: } \texttt{HDFC\_Oct2026.csv} \quad\mid\quad \text{Source Row: } \texttt{\#row-142}$$
   In scanned, multi-page, skewed raster documents, bounding boxes from computer vision models do not cleanly map to discrete, verifiable spreadsheet rows. Generating synthetic row numbers for OCR extracts compromises the auditability and evidentiary value of the analysis.

3. **Credential Vulnerability & Cryptographic Obstacles of Encrypted PDFs:**  
   The overwhelming majority of Indian commercial banks (SBI, HDFC, ICICI, Axis) protect electronic statement PDFs with proprietary encryption passwords (typically combinations of the customer's uppercase PAN and Date of Birth in DDMMYYYY format).  
   Ingesting encrypted PDFs requires FinGenie to collect, decrypt, and manage user financial passwords. This introduces severe security vulnerabilities, expands the attack surface, and risks violating **NFR-04** (passwords must not be stored in plaintext) and **NFR-08** (confidentiality and data protection).

4. **Extreme Computational Latency and Infrastructure Overhead:**  
   High-accuracy deep-learning OCR and document intelligence pipelines (e.g., Donut, LayoutLMv3, AWS Textract) require multi-second GPU inference per page. Processing a 15-page corporate bank statement would take 30 to 60+ seconds and incur substantial recurring cloud infrastructure costs. This directly violates non-functional requirement **NFR-01**, which mandates that standard system actions respond within 3 seconds, and **NFR-02** regarding lean, horizontally scalable processing.

5. **Pragmatic MVP Alternative (The Clean Net-Banking CSV Workaround):**  
   Every major Indian bank (State Bank of India, HDFC, ICICI, Axis, Kotak, PNB, Bank of Baroda) provides a built-in feature to export transaction history directly as a native CSV or Excel (.xlsx) file. In v1.0, FinGenie provides users with interactive, visual in-app net-banking download guides. By educating users to download structured CSV/XLSX exports, FinGenie achieves **100.0% mathematical accuracy at zero OCR infrastructure cost**.

#### 3.3.3 Boundary Conditions for v2.0 Implementation
- Implementation of a client-side (WebAssembly / browser-based) PDF text-layer extractor for digitally generated PDFs (non-scanned), bypassing server-side decryption and credential transmission.
- Introduction of an **Interactive Human-in-the-Loop Verification Interface (FR-24)**: Any scanned document processed by computer vision must render alongside a bounding-box visual comparison UI, requiring the user to confirm or edit detected column mappings and table boundaries before committing records to the verified database.

---

## 4. Secondary Deferred Features & Architectural Scoping

In addition to the three primary deferred capabilities, the engineering team scoped out several secondary features during Sprint 1 and Sprint 2 planning:

| Feature / Requirement ID | Proposed Capability | Engineering Reason for Deferral | Target Milestone |
| :--- | :--- | :--- | :--- |
| **FR-26: Cross-Bank Multi-File Statement Consolidation** | Merging statements from 3+ distinct banks into a single unified financial ledger. | **Contra-Entry Disambiguation:** Inter-account transfers (e.g., transferring ₹50,000 from SBI to HDFC) appear as a ₹50,000 debit in SBI and ₹50,000 credit in HDFC. Without complex cross-statement heuristic matching, naive aggregation counts ₹50,000 in fake revenue and ₹50,000 in fake spending. | **v2.0 (Phase 2)** |
| **Account Aggregator (AA) Real-Time API Sync** | Automated, live bank synchronization via the RBI-licensed Account Aggregator network. | **Regulatory Gateway Hurdles:** Implementing AA requires official certification as a Financial Information User (FIU), substantial recurring licensing costs, and complex OTP-based recurring consent management architectures. | **v2.5 / Commercial** |
| **FR-23: Automated PDF Report Generation** | Server-side PDF export of dashboards and visual financial summaries. | **Prioritizing Deterministic Data Layer:** Relegated to a "stretch" requirement to focus 100% of team engineering capacity on the core calculations, Number Guard safety validation, and API contracts. Users can utilize browser native print-to-PDF (`Ctrl+P`) in v1.0. | **v1.5** |
| **Unsupervised Machine Learning for Spending Categories** | Autonomous K-Means / DBSCAN clustering of transaction descriptions. | **Black-Box Unpredictability:** Unsupervised clustering produces non-deterministic, opaque category tags that cannot be reviewed or audited. Replaced in v1.0 with deterministic, regex-based keyword rules and channel identifiers (UPI, NEFT, IMPS, Card, ATM) with manual user editing (**FR-24, FR-25**). | **v2.0** |

---

## 5. Formal Prioritization Framework (MoSCoW Matrix)

To establish an authoritative, academically defensible boundary for FinGenie, the team evaluated all functional requirements using the **MoSCoW Prioritization Framework** crossed with technical risk analysis:

```
+----------------------------------------------------------------------------------------------------+
|                                    MoSCoW PRIORITIZATION MATRIX                                    |
+-------------------+----------------------------------------------------+---------------------------+
| Priority Tier     | Requirements Included                             | Engineering Justification |
+-------------------+----------------------------------------------------+---------------------------+
| MUST HAVE (M)     | • FR-01: Secure Supabase Auth & Session Handling   | Core platform viability,  |
|                   | • FR-02, 03, 04: Structured CSV/XLSX Ingestion     | mathematical integrity,   |
|                   | • FR-06, 07, 08: Indian Formats (Lakh/Crore, UPI)  | and zero-hallucination    |
|                   | • FR-09: 1-Based Source-Row Traceability           | safety foundation.        |
|                   | • FR-10, 11, 12: Deterministic KPI Engine          |                           |
|                   | • FR-17, 18, 19, 20: Grounded AI & Number Guard    |                           |
+-------------------+----------------------------------------------------+---------------------------+
| SHOULD HAVE (S)   | • FR-21: Multi-Workspace History Management        | Essential for user        |
|                   | • FR-22: Permanent 1-Click Data Purge / Privacy    | retention, auditability,  |
|                   | • FR-24: Manual UI Row & Metadata Correction       | and compliance.           |
|                   | • FR-25: Rule-Based Spend Categorization           |                           |
+-------------------+----------------------------------------------------+---------------------------+
| COULD HAVE (C)    | • FR-13: Short-Term Runway (Gated to >= 90 Days)   | Stretch features that add |
|                   | • FR-23: PDF Report Export Engine                  | user delight without      |
|                   | • Client-side digital PDF text extractor           | risking data corruption.  |
+-------------------+----------------------------------------------------+---------------------------+
| WON'T HAVE (W)    | • Multi-Year Predictive AI/ML Forecasting          | Explicitly excluded to    |
| (Deferred to v2.0)| • Automated Tax Optimization & Statutory Advice    | avoid legal liability,    |
|                   | • Computer Vision OCR for Scanned Paper Statements | high compute costs, and   |
|                   | • Real-Time Account Aggregator Scraping            | epistemic errors.         |
+-------------------+----------------------------------------------------+---------------------------+
```

---

## 6. Phased Implementation Roadmap

FinGenie adopts a staged architectural progression, ensuring that each release builds upon a mathematically verified foundation:

### Phase 1: Core MVP (Current Stable Release — Sprint 1, 2 & 3)
- **Ingestion:** Native Indian CSV and XLSX bank statements and balance sheets.
- **Arithmetic Engine:** 100% deterministic Python `Decimal` calculations (28-digit precision, no floating-point rounding errors).
- **Traceability:** Full source attribution mapping calculated metrics to 1-based source spreadsheet rows (`source_rows=[142]`).
- **AI Safety:** Decoupled architecture with zero-math LLM prompt injection and post-generation regex assertion via the **Numeric Verification Guard** (`verify_tool_results_text`).
- **Privacy:** Ephemeral session analysis option, client-side PII masking before external API transmission, and 1-click permanent data deletion (**FR-22**).

### Phase 1.5: Analytical Stabilization & Usability (Post-MVP Interim Release)
- **Gated Runway Projections (FR-13):** Deterministic cash burn rate and survival runway calculations activated strictly when $\ge 90$ days of continuous transaction history are verified.
- **Digital PDF Text Extraction:** Client-side, in-browser text parsing for digitally generated PDF bank statements (excluding scanned images), with no password storage.
- **Clean PDF Dashboard Reports (FR-23):** Print-ready vector PDF report exports containing KPI cards, charts, and audit provenance tables.

### Phase 2.0: Commercial Expansion & Intelligent Ingestion (v2.0 Milestone)
- **Human-in-the-Loop OCR Engine:** Optical character recognition for scanned statements paired with an interactive bounding-box correction UI (**FR-24**).
- **Cross-Bank Reconciliation (FR-26):** Algorithmic contra-entry matching to deduplicate inter-account funds transfers across multi-statement uploads.
- **Tax Preparation Export Module:** Pre-computed expense classification reports formatted for Tally, Zoho Books, and CA tax-audit review (strictly disclaiming autonomous advisory).
- **Account Aggregator Sandbox Integration:** Pilot consent-based automated bank statement fetching under the RBI NBFC-AA architecture.

---

## 7. Viva & Academic Defense Guide: Key Conceptual Takeaways

For academic examinations, project vivas, and faculty evaluations, examiners frequently test whether students understand the boundaries of their system and why certain complex features were omitted. Below is a structured conceptual guide for defending these engineering decisions without needing architectural diagrams:

### Question 1: "Why did your team not implement AI-driven multi-year financial forecasting?"
* **Core Architectural Defense:**  
  *"We deliberately avoided multi-year forecasting in v1.0 due to the fundamental **'Snapshot vs. Flow' accounting fallacy**. A balance sheet is a static, point-in-time snapshot containing zero velocity data. In our software engineering specification, under functional requirement **FR-13**, we enforced **Data Sufficiency Gating**: predictive models require a minimum of 90 days of continuous transaction flow or two consecutive fiscal years of comparative audited statements.*  
  *Extrapolating a 3-year or 5-year balance trajectory from a single monthly statement creates an uncontrolled quadratic variance explosion ($O(t^2)$). Presenting an unreliable projection with false certainty to retail users violates our core principle of mathematical auditability and deterministic reproducibility."*

### Question 2: "Why does FinGenie not calculate tax savings or recommend tax deductions?"
* **Core Architectural Defense:**  
  *"There are two definitive software engineering and legal barriers: **Statutory Non-Compliance** and **Information Asymmetry in Bank Narrations**.*  
  *First, under the Indian Income Tax Act and SEBI regulations, automated tax advice constitutes professional advisory practice requiring statutory Chartered Accountant certification. Erroneous algorithmic advice exposes the system to legal liability.*  
  *Second, bank statement narrations show payment settlement strings (such as UPI IDs or IMPS codes), not underlying legal tax invoices. A statement does not indicate whether a ₹20,000 transfer was an operational business expense, capital asset, or personal gift, nor does it contain GSTINs or HSN codes. Without tax invoices, computing deductions is pure speculation. FinGenie strictly follows requirement **FR-20**, functioning as a verified financial analysis platform while explicitly disclaiming statutory tax and investment advisory."*

### Question 3: "Why did you restrict uploads to CSV and XLSX instead of allowing scanned PDFs or mobile camera photos via OCR?"
* **Core Architectural Defense:**  
  *"In computer vision, an OCR character error rate of 1% is acceptable; in financial accounting, **a 1% error rate is catastrophic**. A single misread digit—such as confusing an '8' for a '0' or dropping a decimal point—completely breaks our fundamental bank reconciliation equation ($\text{Opening} + \text{Inflows} - \text{Outflows} = \text{Closing}$) and balance sheet equality ($\text{Assets} = \text{Liabilities} + \text{Equity}$).*  
  *Furthermore, OCR destroys our signature guarantee of **1-based source-row provenance (FR-09)**, because bounding boxes in scanned images cannot be reliably mapped to immutable spreadsheet row numbers.*  
  *Finally, almost all Indian bank statement PDFs are password-encrypted with users' personal PAN or Date of Birth. Handling encrypted PDFs would force us to collect and store user credentials, violating our privacy and security constraints (**NFR-04, NFR-08**). We solved this pragmatically by providing net-banking CSV export guides, ensuring 100% mathematical accuracy at zero OCR infrastructure cost."*

### Question 4: "What is the primary software engineering lesson your team learned from scoping out these features?"
* **Core Architectural Defense:**  
  *"The primary lesson is that **good software engineering is defined by knowing what to say 'NO' to**. Premature feature expansion (scope creep) without mathematical grounding or regulatory clarity produces brittle, unsafe systems. By establishing strict boundary conditions, MoSCoW prioritization, and deterministic decoupled AI architecture, our team delivered a robust, 100% verified financial analysis platform that users can genuinely trust with their money."*

---

## 8. Conclusion

The exclusion of multi-year forecasting, tax optimization, and paper OCR from FinGenie v1.0 represents a deliberate, principled engineering strategy rather than an omission of capability. By prioritizing **exact arithmetic precision (`Decimal`), absolute source-row auditability (`#row-142`), robust Indian banking compatibility, and deterministic zero-math AI safety**, FinGenie delivers a production-grade financial analysis system that achieves maximum reliability. The boundary conditions and requirements established in this document provide a clear, unambiguous roadmap for their structured implementation in v2.0.
