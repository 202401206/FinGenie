"""Numeric support, notation, evidence eligibility and explicit units."""

from dataclasses import dataclass
from decimal import Decimal, localcontext

import pytest

from app.ai.number_guard import verify_numbers_in_text, verify_tool_results_text


@dataclass
class ToolResult:
    name: str
    value: object
    unit: str
    calculation_id: str
    status: str


def result(value=Decimal("5000"), unit="INR", status="available"):
    return ToolResult(
        name="bank_total_credit",
        value=value,
        unit=unit,
        calculation_id="bank.total_credit.v1",
        status=status,
    )


@pytest.mark.parametrize(
    "text,value,unit",
    [
        ("Credits: INR 5000, confirmed.", "5000", "INR"),
        ("Credits: INR 5,000.", "5000", "INR"),
        ("Credits: ₹5,000.00.", "5000", "INR"),
        ("Credits: 5000 INR.", "5000", "INR"),
        ("Credits: Rs. 5000.", "5000", "INR"),
        ("Credits: 1,25,000.", "125000", "INR"),
        ("Credits: 125,000.", "125000", "INR"),
        ("Net flow: INR -5000.", "-5000", "INR"),
        ("Net flow: −5000.", "-5000", "INR"),
        ("Net flow: (INR 5000).", "-5000", "INR"),
        ("Net flow: (5000 INR).", "-5000", "INR"),
        ("Net flow: +5000.", "5000", "INR"),
        ("Ratio: 1.88.", "1.88", "ratio"),
        ("Credits: $5000.", "5000", "USD"),
        ("Change: 5%.", "5", "percent"),
        ("Credits: 0.", "0", "INR"),
        ("Credits: 0.00000001.", "0.00000001", "INR"),
    ],
)
def test_supported_notation(text, value, unit):
    assert verify_tool_results_text(text, [result(Decimal(value), unit)]).valid


@pytest.mark.parametrize(
    "text",
    [
        "Credits: -₹5000.",
        "Credits: 5000 K.",
        "Credits: 5000‰.",
        "Credits: 5500.",
        "Credits: -5000.",
        "Credits: USD 5000.",
        "Credits: 5000 EUR.",
        "Credits: ₹5000 USD.",
        "Credits: 5000%.",
        "Credits: 5000 percent.",
        "Credits: 5000 lakh.",
        "Credits: 5000k.",
        "Credits: five thousand.",
        "Credits: 5e3.",
        "Credits: 50,00.",
        "Credits: 5000.01.",
        "Credits: 5000..00.",
        "Credits: .5000.",
        "Credits: ５０００.",
        "Credits: NaN.",
        "Credits: infinity.",
        "Credits: (5000).",
        "Credits: (-5000).",
        "Credits: --5000.",
        "During 2026: credits were 5000.",
        "1. Credits: 5000.",
        "Credits: 5000/5000.",
        "Credits: 5000:5000.",
        "Credits: 5000-5000.",
        "Credits: abc5000.",
        "",
        "   ",
    ],
)
def test_rejects_unsupported_numbers_and_formats(text):
    assert not verify_tool_results_text(text, [result()]).valid


@pytest.mark.parametrize(
    "value,status",
    [
        (None, "available"),
        (Decimal("5000"), "unavailable"),
        (5000.0, "available"),
        ("5000", "available"),
        (True, "available"),
        (Decimal("NaN"), "available"),
        (Decimal("Infinity"), "available"),
    ],
)
def test_invalid_or_unavailable_evidence_cannot_authorize_a_number(value, status):
    assert not verify_tool_results_text(
        "Credits: 5000.", [result(value, status=status)]
    ).valid


def test_missing_value_does_not_authorize_zero():
    assert not verify_tool_results_text("Credits: 0.", [result(None)]).valid


def test_no_tools_cannot_authorize_a_number():
    assert not verify_tool_results_text("Credits: 5000.", []).valid


def test_non_numeric_reply_needs_no_tools():
    assert verify_tool_results_text(
        "Hello! I can explain your financial data.", []
    ).valid


def test_collects_all_unsupported_figures():
    check = verify_tool_results_text("Credits: 5500; debits: 6000.", [result()])
    assert [issue.token for issue in check.issues] == ["5500", "6000"]


def test_exact_large_integer_without_float_rounding():
    value = 9007199254740993
    assert verify_tool_results_text(str(value), [result(value)]).valid
    assert not verify_tool_results_text(str(value - 1), [result(value)]).valid


def test_numeric_membership_does_not_verify_metric_identity():
    # Explicit limitation: value membership alone cannot distinguish credit/debit.
    assert verify_tool_results_text("Debits: 5000.", [result()]).valid


@pytest.mark.parametrize("keyword", ["verified_numbers", "allowed_numbers"])
def test_team_interface_accepts_both_documented_parameter_names(keyword):
    assert (
        verify_numbers_in_text("Credits: INR 5,000.", **{keyword: [Decimal("5000")]})
        is True
    )
    assert (
        verify_numbers_in_text(
            "Credits: INR 999999999.", **{keyword: [Decimal("5000")]}
        )
        is False
    )


def test_team_interface_positional_parameters():
    assert verify_numbers_in_text("Credits: 5000.", [Decimal("5000")]) is True


@pytest.mark.parametrize(
    "values",
    [
        None,
        [None],
        [True],
        [5000],
        [5000.0],
        ["5000"],
        [Decimal("NaN")],
        [Decimal("sNaN")],
        [Decimal("Infinity")],
        (Decimal("5000"),),
    ],
)
def test_team_interface_rejects_invalid_evidence(values):
    assert verify_numbers_in_text("Credits: 5000.", values) is False


def test_conflicting_aliases_fail_closed():
    assert (
        verify_numbers_in_text(
            "Credits: 5000.", [Decimal("5000")], allowed_numbers=[Decimal("5000")]
        )
        is False
    )


def test_no_evidence_allows_greeting_but_not_numbers():
    assert verify_numbers_in_text("Hello!", []) is True
    assert verify_numbers_in_text("Credits: 0.", []) is False


def test_numeric_only_interface_cannot_verify_currency():
    # This limitation is intrinsic to the published list[Decimal] contract.
    assert verify_numbers_in_text("Credits: USD 5000.", [Decimal("5000")]) is True
    assert not verify_tool_results_text("Credits: USD 5000.", [result()]).valid


def test_accounting_sign_does_not_round_under_decimal_context():
    value = Decimal("-123456789012345678901234567890.123456789")
    with localcontext() as context:
        context.prec = 6
        assert (
            verify_numbers_in_text(
                "(123456789012345678901234567890.123456789)", [value]
            )
            is True
        )


@pytest.mark.parametrize("text", [None, 123, "x" * 20001, "9" * 129])
def test_invalid_or_oversized_text_fails_closed(text):
    assert verify_numbers_in_text(text, [Decimal("5000")]) is False
