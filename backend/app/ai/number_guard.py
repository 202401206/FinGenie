"""Conservative numeric-literal checks against this response's tool results.

This verifies numeric support, not prose meaning or the underlying calculations.
Unsupported notation is rejected, never silently rounded or converted.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, Sequence


class ToolEvidence(Protocol):
    """Structural interface: no dependency on the unmerged AI tool module."""

    value: object
    unit: str
    status: str


# Read a whole numeric-looking token before validating its punctuation/grouping.
NUMBER = re.compile(r"[+\-−]?(?:\d(?:[\d,]*\d)?(?:\.\d+)?|\.\d+)(?:[eE][+\-]?\d+)?")
GROUPED = re.compile(
    r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+|[0-9]{1,2}(?:,[0-9]{2})*,[0-9]{3})(?:\.[0-9]+)?"
)
CURRENCY = r"(?:[A-Z]{3}|₹|\$|€|£|¥|Rs\.?)"
SYMBOLS = {"₹": "INR", "Rs": "INR", "Rs.": "INR", "$": "USD", "€": "EUR", "£": "GBP"}
# These formats need explicit policy/support; do not treat '5 lakh' as '5'.
WORDS = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
    r"forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|"
    r"lakh|lakhs|crore|crores|nan|infinity|inf)\b|∞",
    re.I,
)


@dataclass(frozen=True)
class GuardIssue:
    token: str
    reason: str


@dataclass(frozen=True)
class VerificationResult:
    issues: tuple[GuardIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues


def verify_tool_results_text(
    text: str, tool_results: Sequence[ToolEvidence]
) -> VerificationResult:
    """Check digit-based literals against available, finite Decimal/int results.

    No tolerance, floats, strings, missing-value substitution or implicit scaling.
    Currency prefixes/suffixes and percent signs constrain matching units. Bare
    numbers can match any result, so metric-label correctness is NOT guaranteed.
    Dates, list numbering and number words are deliberately not allowlisted.
    """
    evidence = []
    for result in tool_results:
        value = result.value
        if result.status != "available" or type(value) not in (int, Decimal):
            continue
        value = Decimal(value)
        if value.is_finite():
            evidence.append((value, result.unit))

    return _verify(text, evidence)


def verify_numbers_in_text(
    ai_text: str,
    verified_numbers: list[Decimal] | None = None,
    *,
    allowed_numbers: list[Decimal] | None = None,
) -> bool:
    """Team contract: numeric support only, returning an actual bool.

    `allowed_numbers` is a compatibility alias for the guide's call example.
    Supply exactly one name. Invalid evidence fails closed. Units and metric
    identity cannot be established from a bare list of Decimal values.
    """
    if verified_numbers is not None and allowed_numbers is not None:
        return False
    numbers = verified_numbers if verified_numbers is not None else allowed_numbers
    if not isinstance(numbers, list) or any(
        not isinstance(value, Decimal) or not value.is_finite() for value in numbers
    ):
        return False
    return _verify(ai_text, [(value, None) for value in numbers]).valid


def _verify(
    text: str, evidence: Sequence[tuple[Decimal, str | None]]
) -> VerificationResult:
    if not isinstance(text, str) or not text.strip():
        return VerificationResult((GuardIssue("", "The answer is empty."),))
    if len(text) > 20000:
        return VerificationResult((GuardIssue("", "The answer is too long."),))

    issues = [
        GuardIssue(m.group(), "Use full numeric digits, without scale words.")
        for m in WORDS.finditer(text)
    ]
    for match in NUMBER.finditer(text):
        raw = match.group()
        unsigned = raw.lstrip("+-−")
        before, after = text[: match.start()], text[match.end() :]
        if len(raw) > 128 or not GROUPED.fullmatch(unsigned):
            issues.append(GuardIssue(raw, "Unsupported number format."))
            continue
        # Reject fragments of dates, ratios, exponents, identifiers, ranges,
        # malformed decimals, units such as 5k, and non-ASCII digit formats.
        left = before[-1:]
        right = after[:1]
        if (left and (left.isalnum() or left in "_./:+-−")) or (
            right
            and (
                right.isalnum()
                or right in "_/:+-−"
                or (right == "." and after[1:2] == ".")
            )
        ):
            issues.append(
                GuardIssue(raw, "Use standalone numbers, not dates or shorthand.")
            )
            continue
        prefix = re.search(rf"({CURRENCY})\s*$", before)
        suffix = re.match(rf"\s*({CURRENCY})(?!\w)", after)
        if prefix and before[: prefix.start()].rstrip().endswith(("-", "+", "−")):
            issues.append(GuardIssue(raw, "Place the sign directly before the digits."))
            continue
        if re.match(r"\s*(?:[kKmMbB]\b|‰)", after):
            issues.append(GuardIssue(raw, "Unsupported shorthand or unit."))
            continue
        units = []
        for currency in (prefix, suffix):
            if currency:
                code = currency.group(1)
                units.append(SYMBOLS.get(code, code))
        if re.match(r"\s*(?:%|percent\b|per cent\b)", after, re.I):
            units.append("percent")
        value = Decimal(raw.replace(",", "").replace("−", "-"))
        # Accounting notation: (INR 500) or (500) means a negative amount.
        opening = before[: prefix.start()] if prefix else before
        closing = after[suffix.end() :] if suffix else after
        if opening.rstrip().endswith("(") and closing.lstrip().startswith(")"):
            if raw.startswith(("+", "-", "−")):
                issues.append(
                    GuardIssue(raw, "Do not combine signs and accounting brackets.")
                )
                continue
            value = value.copy_negate()
        if not any(
            value == known
            and (known_unit is None or all(unit == known_unit for unit in units))
            for known, known_unit in evidence
        ):
            issues.append(
                GuardIssue(
                    raw,
                    "No available tool result matches this value and explicit unit.",
                )
            )
    return VerificationResult(tuple(issues))
