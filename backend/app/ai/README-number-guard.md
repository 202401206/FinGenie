# FinGenie — Number Guard

**Prepared by:** S Srujan

**Contribution:** AI summaries and numerical verification

## Purpose

Number Guard checks whether numbers in an AI-written answer match the supplied
calculation results. For example, credits of INR 5,000 do not support an answer
claiming INR 5,500. The checker returns `False` for the unsupported answer.

This module follows the AI + Analysis team's integration contract. It has no
LLM, API, database or financial-calculation dependency, and can be merged into
`main` independently of the AI integration branch.

## Files

| File | Responsibility |
|---|---|
| [number_guard.py](number_guard.py) | Numeric parsing, exact Decimal comparisons, boolean interface and optional unit-aware checks. |
| [test_number_guard.py](../../tests/ai/test_number_guard.py) | Automated checks for supported notation, unsupported numbers, invalid inputs, precision and both contract parameter names. |

## Setup and tests

Requires Python 3.11 or later. From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
cd backend
python -m pytest tests/ai/test_number_guard.py -q
python -m ruff check app/ai/number_guard.py tests/ai/test_number_guard.py
```

On Windows, use `py -m venv .venv` and `.\.venv\Scripts\Activate.ps1` to create
and activate the environment. The checker and its tests need no API key.
Run `python -m pytest -q` from `backend` for the complete backend suite.

Verified on 31 October 2026: **143 guard cases passed**, **212 total backend
cases passed** after merging the current main branch, and Ruff passed. Parameterized inputs
count as separate cases. The suite emitted a non-failing Starlette/httpx
deprecation warning.

## Required team interface

```python
from decimal import Decimal
from app.ai.number_guard import verify_numbers_in_text

values = [Decimal("5000")]
assert verify_numbers_in_text("Credits: INR 5,000.", values) is True
assert verify_numbers_in_text("Credits: INR 5,500.", values) is False
```

Both keyword spellings in the team's guide are accepted:

```python
verify_numbers_in_text(ai_text="Credits: 5000.", verified_numbers=values)
verify_numbers_in_text(ai_text="Credits: 5000.", allowed_numbers=values)
```

Supply exactly one list. `allowed_numbers` is a compatibility alias, not another
source of evidence. Supplying both returns `False`. The return type is an actual
`bool`, not a result object.

Only finite `Decimal` values are valid in this interface. Missing values,
float/string/integer/boolean entries, and non-finite values fail closed. The
caller must supply available results from the current request, never numbers
copied from the AI or user message. Missing results must not become zero.
An empty list permits ordinary text without numbers, but cannot authorize zero.

## Optional unit-aware checking

The required `list[Decimal]` interface contains no currency or metric metadata.
To retain currency checks when actual tool results are available, use:

```python
from app.ai.number_guard import verify_tool_results_text

check = verify_tool_results_text(draft, executed_tools)
if not check.valid:
    for issue in check.issues:
        print(issue.token, issue.reason)
```

Each supplied object needs `value`, `unit` and `status` attributes, matching the
AI module's `ToolResult`. No import from that module is required. Eligible
values are finite `Decimal` or integer values with `status="available"`.
Unavailable and invalid values are excluded. The returned `VerificationResult`
contains `.valid` and `.issues`; use `.valid`, not the object itself, as a boolean.

An explicit currency or percentage unit must match the evidence in this mode.
For example, `USD 5000` is rejected for an INR result. Bare numbers still match
any eligible metric, so units should be explicit in generated text.

## Number formats

| Text | Interpretation / policy |
|---|---|
| `5000`, `5,000.00` | Equivalent exact values; no rounding tolerance. |
| `1,25,000`, `125,000` | Indian and Western grouping are supported. |
| `INR -5000`, `−5000` | Negative values; sign must match. |
| `(INR 5000)` | Accounting notation for a negative amount. |
| `₹5000`, `Rs. 5000`, `5000 INR` | Supported currency notation; codes are uppercase. |
| `5k`, `5 lakh`, `5e3`, `five thousand` | Rejected rather than silently converted. |
| `NaN`, `Infinity`, malformed grouping | Rejected. |

Place signs directly before digits. Separated signs such as `- 5000`,
`− 5000` and `INR - 5000` are rejected rather than treated as positive. `$` means USD in unit-aware mode; `¥` is not
mapped to a currency. Percentages require unit `percent` in unit-aware mode;
ratios are not converted. Dates and list numbering are not exempted from checks.
Empty answers and text longer than 20,000 characters are rejected.

For dash bullets, include a label before the amount: `- Total credits: INR 5000`
is accepted. A numeric-only bullet such as `- 5000 INR` is rejected because the
dash is indistinguishable from a detached negative sign. Do not strip such signs
before checking; doing so could turn a negative claim into a positive amount.

## Integration ownership

The Number Guard only returns a checking decision. The AI integration layer
owns the following workflow:

```text
Calculate results → Generate draft → Check draft
                                     ├─ Pass: return answer
                                     └─ Fail: request one correction → Check again
                                                                        ├─ Pass: return answer
                                                                        └─ Fail: HTTP 502
```

The final error code is `ai_validation_failed`, as requested in the team guide.
This standalone module does not raise HTTP errors or make provider calls.
Local, unpushed branch `feat/number-guard-integration` contains experimental
wiring, retry/error handling and live demonstrations on top of the AI branch.
The shared AI branch owns the final integration.

## Limits

- Numeric membership does not verify metric meaning. “Debits were 5000” may
  pass when the evidence contains a credit of 5000.
- The boolean interface cannot verify currency: `USD 5000` can match a bare
  `Decimal("5000")`. Use the richer check when unit information exists.
- The guard trusts the supplied calculations. It does not recompute totals,
  inspect original documents or validate source references/reporting periods.
- Non-numeric claims and general prose meaning are not checked. Known number
  words are rejected, but this is not a complete natural-language parser.
- Conservative formatting rules may reject valid prose. Prompts should request
  full numeric digits, explicit currencies and no extra dates or numbered lists.

A passing result means supported numeric literals, not a guarantee that every
claim in the answer is correct. Automated tests are deterministic; live model
behaviour is verified separately in the integration branch.
