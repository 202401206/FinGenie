# FinGenie — Mutation Testing Report

**Prepared by S Srujan · AI and Analysis Team**

## 1. Purpose of this work

FinGenie calculates financial figures and uses AI to explain them. Its tests need to detect mistakes in those calculations and in Number Guard, which checks whether the numbers in an AI answer match the supplied calculation results.

A test can pass because the program works correctly. However, it can also pass because the test does not check enough. This report examines that second possibility by deliberately introducing small mistakes into copies of the code and checking whether the tests detect them.

The initial tests detected **15 of 16 deliberately introduced faults**. After adding a test for the missed case, they detected **all 16**.

## 2. How mutation testing works

A *mutation* is a small, deliberate change to the code. The changed copy is called a *mutant*.

Consider a bank statement with ₹5,000 in credits and ₹2,500 in debits. The correct net cash flow is ₹2,500. Changing the subtraction to addition produces ₹7,500. A test that checks the expected ₹2,500 should fail when it runs against that changed code. That failure shows that the test detected the mistake.

The following terms describe the outcomes.

| Term | Meaning in this report |
| --- | --- |
| Killed, or detected | At least one test fails because of the deliberate change. |
| Survived, or missed | All tests still pass despite the change. The case needs investigation. |
| Equivalent mutant | A change that produces the same behavior for every supported input. |
| Mutation score | The percentage of executable mutants detected by the tests. |

A higher score means the tests detected more of the selected faults.

## 3. Parts of FinGenie tested

| Part | Responsibility | Example mistake introduced |
| --- | --- | --- |
| Number Guard | Checks numeric values, explicit currencies, signs and supported formats in AI answers | Allowing USD 5,000 when the supplied result is INR 5,000 |
| Bank-statement analytics | Calculates incoming money, outgoing money, net cash flow and balance reconciliation | Adding outgoing money when checking the closing balance |
| Balance-sheet analytics | Calculates working capital, current ratio and the accounting balance difference | Multiplying assets by liabilities when calculating current ratio |

Sixteen faults were selected across these three parts. Each was applied separately in a temporary copy. The original program was run first to confirm that the selected tests passed before any faults were introduced.

## 4. Procedure followed

1. Run the selected tests against the original code.
2. Introduce one deliberate change into a temporary copy.
3. Run the same tests and record whether they detect it.
4. Restore the original code before trying the next change.
5. Investigate any surviving change and add a test for the missed behavior.
6. Repeat the selected campaign with the improved tests.

The runner records failures, surviving changes, execution errors and timeouts separately. A setup error does not count as a detected fault. Every run in this campaign completed successfully.

## 5. Results

| Stage | Tests passing on original code | Faults introduced | Detected | Missed | Mutation score |
| --- | ---: | ---: | ---: | ---: | ---: |
| Before improvement | 273 | 16 | 15 | 1 | 93.75% |
| After improvement | 274 | 16 | 16 | 0 | 100% |

The calculation for the final score is **16 detected faults ÷ 16 executable faults × 100 = 100%**. No mutants were excluded as equivalent, invalid or timed out.

This result covers the 16 selected changes. A larger selection could reveal further test gaps.

## 6. The missed case and how it was fixed

Number Guard accepts a numeric token containing up to 128 characters. A numeric token is the portion of the answer representing a number, including any supported sign or punctuation.

The surviving change, identified as **NG07**, increased that limit from 128 to 129. The existing tests did not check this exact boundary, so they accepted both versions of the program.

A new test now supplies matching calculation evidence and checks both sides of the limit.

| Input | Expected behavior | Reason |
| --- | --- | --- |
| A 128-digit amount | Accept | It is within the supported limit. |
| A 129-digit amount | Reject | It exceeds the supported limit. |

Matching evidence is supplied for both amounts so that the test isolates the length rule. These unusually large values exercise a software boundary. They are synthetic test inputs.

With this test added, the version allowing 129 characters fails. All 15 previously detected faults are still detected. The improvement consists of one additional test function.

## 7. Types of changes used

| Name | Explanation | Example from this campaign |
| --- | --- | --- |
| Arithmetic Operator Replacement (AOR) | Changes a mathematical operation | Subtraction becomes addition in net cash flow. |
| Relational Operator Replacement (ROR) | Changes a comparison or decision | Equality becomes inequality in value matching. |
| Boundary change | Moves a comparison limit | The token limit increases from 128 to 129. |
| Statement Deletion (SDL) | Removes an instruction | The explicit currency constraint is removed. |

The runner groups boundary and validity-decision changes under ROR. The descriptions below identify the exact behavior changed.

## 8. Record of the 16 selected faults

| ID | Deliberate change | First run | Final run |
| --- | --- | --- | --- |
| NG01 | Reverse the exact-value comparison | Detected | Detected |
| NG02 | Reverse the available-result status check | Detected | Detected |
| NG03 | Increase the answer-length limit by one character | Detected | Detected |
| NG04 | Remove the negative sign implied by accounting brackets | Detected | Detected |
| NG05 | Remove the explicit currency constraint | Detected | Detected |
| NG06 | Remove the percentage-unit constraint | Detected | Detected |
| NG07 | Increase the numeric-token limit from 128 to 129 | Missed | Detected |
| NG08 | Reverse the final valid/invalid decision | Detected | Detected |
| BK01 | Subtract credits while accumulating incoming money | Detected | Detected |
| BK02 | Subtract debits while accumulating outgoing money | Detected | Detected |
| BK03 | Add credits and debits to calculate net cash flow | Detected | Detected |
| BK04 | Add outgoing money when checking the closing balance | Detected | Detected |
| BS01 | Add current liabilities when calculating working capital | Detected | Detected |
| BS02 | Multiply instead of divide when calculating current ratio | Detected | Detected |
| BS03 | Reverse the zero-liabilities check | Detected | Detected |
| BS04 | Add liabilities and equity to assets in the balance-difference calculation | Detected | Detected |

The IDs beginning with NG refer to Number Guard, BK to bank analytics and BS to balance-sheet analytics.

## 9. Overall verification

After adding the boundary test and the security tests described in the companion report, the full backend suite passed with **901 tests and zero skips**. The run reported one existing library deprecation warning. Lint and formatting checks passed for the five added Python files.

The selected mutation campaign demonstrates sensitivity to the listed faults. Further checks are needed to evaluate other fault types, deployed services and behavior with real uploaded documents.

## 10. Technical details and reproduction

Testing used Python 3.14.6 on macOS ARM64 on 22 November 2026. The tested repository revision was `9580ca0dcdee8ebe28753a5c4439a36340040b9d`.

From the repository root, install the local database test dependency.

```sh
npm ci --prefix supabase/tests
```

Then, from the `backend` folder, run the following commands in order.

```sh
python -m pip install -r requirements-dev.txt
python -m scripts.run_mutation_testing --output ../docs/testing-evidence/mutation-initial-new.json
python -m scripts.run_mutation_testing --include-regressions --baseline ../docs/testing-evidence/mutation-initial-new.json --output ../docs/testing-evidence/mutation-final-new.json
python -m pytest -q
```

The first mutation command reproduces the initial campaign. The second adds the boundary regression and includes the explicitly supplied baseline in its evidence file. The runner checks that both campaigns used the same source hashes before combining them. Each mutation has a 60-second test-run limit. The selected tests cover Number Guard and both analytics modules.

A follow-up verification on 23 November 2026 reran both campaigns after hardening the runner. The results remained 15/16 initially and 16/16 with the boundary regression. Before each execution, the runner removes the previous JUnit result. Missing or malformed results are classified as invalid. This prevents an earlier failure from being counted against a later mutation.

Every run writes a timestamped file by default. The optional output path must identify a new file, preserving earlier evidence. Additional runner tests cover stale results, malformed output and overwrite protection.

The saved evidence contains the exact source changes, original source hashes, failed test names and test output. Its Git revision identifies the checkout used for revalidation. The production source hashes identify the financial code tested.

- [Mutation runner](../backend/scripts/run_mutation_testing.py)
- [New boundary test](../backend/tests/ai/test_number_guard_mutation_regression.py)
- [Initial and final mutation results](testing-evidence/mutation-results.json)
- [Full backend test output](testing-evidence/backend-tests.txt)
