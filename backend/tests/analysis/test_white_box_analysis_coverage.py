"""White-box testing suite for FinGenie Analysis engines.

Targets 100% statement, branch, and boundary condition coverage across:
- app.analysis.balance_sheet_kpis
- app.analysis.bank_kpis
"""

from decimal import Decimal, InvalidOperation

import pytest

from app.analysis.balance_sheet_kpis import (
    _extract_line_items_total,
    _get_document_metadata,
    analyze_balance_sheet,
    calculate_balance_difference,
    calculate_current_ratio,
    calculate_working_capital,
)
from app.analysis.balance_sheet_kpis import (
    _to_decimal as bs_to_decimal,
)
from app.analysis.balance_sheet_kpis import (
    serialize_analysis_result as bs_serialize,
)
from app.analysis.bank_kpis import (
    _get_source_metadata,
    calculate_balance_reconciliation,
    calculate_bank_kpis,
    calculate_closing_balance,
    calculate_net_cash_flow,
    calculate_opening_balance,
    calculate_total_credit,
    calculate_total_debit,
)
from app.analysis.bank_kpis import (
    _to_decimal as bank_to_decimal,
)
from app.analysis.bank_kpis import (
    serialize_analysis_result as bank_serialize,
)


# ---------------------------------------------------------------------------
# 1. White-box tests for app.analysis.balance_sheet_kpis
# ---------------------------------------------------------------------------
def test_balance_sheet_helper_type_guards_and_conversions() -> None:
    """Branch coverage for balance_sheet_kpis conversion and extraction helpers."""
    # Boolean rejected
    assert bs_to_decimal(True) is None
    assert bs_to_decimal(False) is None

    # Blank / commas only rejected
    assert bs_to_decimal(" , , ") is None
    assert bs_to_decimal("") is None
    assert bs_to_decimal(None) is None

    # Non-numeric string caught by except block
    assert bs_to_decimal("abc_not_a_number") is None

    # Valid string and numeric conversions
    assert bs_to_decimal(" 1,500.50 ") == Decimal("1500.50")
    assert bs_to_decimal(250) == Decimal("250")

    # Document metadata non-dict guards
    assert _get_document_metadata("not-a-dict") == ("", None)
    assert _get_document_metadata({"source_metadata": "not-a-dict"}) == ("", None)

    # Line item extraction guards
    tot, rows, paths = _extract_line_items_total("not-a-list", "assets")
    assert tot == Decimal("0") and rows == [] and paths == []

    # Line item list with non-dict items and negative source rows
    mixed_items = [
        None,
        "not-a-dict",
        {"value": 500, "source_row": 10},
        {"value": "invalid", "source_row": -1},
        {"value": 250, "source_row": 0},
    ]
    tot2, rows2, paths2 = _extract_line_items_total(mixed_items, "liabilities")
    assert tot2 == Decimal("750")
    assert rows2 == [10]


def test_balance_sheet_kpi_error_and_boundary_branches() -> None:
    """Branch coverage for balance sheet KPI edge cases and pipeline reliability."""
    # Current ratio with zero liabilities
    zero_liab_data = {
        "currency": "INR",
        "assets": {
            "current": [{"line_item": "Cash", "value": 100000, "source_row": 1}]
        },
        "liabilities": {"current": []},
    }
    cr_res = calculate_current_ratio(zero_liab_data)
    assert cr_res["status"] == "unavailable"
    assert "division by zero" in cr_res["reason"].lower()

    # Non-dict statement data guard
    assert calculate_current_ratio("not-a-dict")["status"] == "unavailable"
    assert calculate_working_capital("not-a-dict")["status"] == "unavailable"
    assert calculate_balance_difference("not-a-dict")["status"] == "unavailable"

    # Missing assets or liabilities dict (line 133, 213, 306)
    assert (
        calculate_current_ratio({"assets": "not-dict", "liabilities": {}})["status"]
        == "unavailable"
    )
    assert (
        calculate_working_capital(
            {"unit_scale": 1, "assets": "not-dict", "liabilities": {}}
        )["status"]
        == "unavailable"
    )
    assert (
        calculate_balance_difference(
            {"assets": {}, "liabilities": "not-dict", "equity": {}}
        )["status"]
        == "unavailable"
    )

    # Working capital with missing current liabilities
    no_liab_data = {
        "currency": "INR",
        "unit_scale": 1,
        "assets": {
            "current": [{"line_item": "Cash", "value": 100000, "source_row": 1}]
        },
        "liabilities": {"current": []},
    }
    wc_res = calculate_working_capital(no_liab_data)
    assert wc_res["status"] == "available"
    assert wc_res["value"] == Decimal("100000")

    # Reconciliation check with missing totals
    missing_totals = {
        "currency": "INR",
        "assets": {},
        "liabilities": {},
        "equity": {},
    }
    diff_res = calculate_balance_difference(missing_totals)
    assert diff_res["status"] == "unavailable"

    # Full pipeline: diff unavailable -> reliability = insufficient_data
    pipe_insufficient = analyze_balance_sheet(missing_totals)
    assert pipe_insufficient["reliability"] == "insufficient_data"
    assert len(pipe_insufficient["warnings"]) >= 1

    # Full pipeline non-dict input (line 396)
    pipe_non_dict = analyze_balance_sheet("not-a-dict")
    assert pipe_non_dict["reliability"] == "insufficient_data"

    # Full pipeline: diff != 0 -> reliability = unreliable
    unbalanced_data = {
        "currency": "INR",
        "unit_scale": 1,
        "assets": {
            "current": [{"line_item": "Cash", "value": 1000, "source_row": 1}],
            "total": 5000,
        },
        "liabilities": {
            "current": [{"line_item": "Payables", "value": 500, "source_row": 2}],
            "total": 2000,
        },
        "equity": {"total": 2000},
    }
    pipe_unreliable = analyze_balance_sheet(unbalanced_data, include_current_ratio=True)
    assert pipe_unreliable["reliability"] == "unreliable"
    assert "Balance sheet reconciliation failed" in pipe_unreliable["warnings"][0]

    # Serialization guards
    assert bs_serialize("not-a-dict") == "not-a-dict"
    raw_analysis = {
        "metrics": [
            "not-a-dict-metric",
            {"key": "working_capital", "value": Decimal("1000.00")},
            {"key": "current_ratio", "value": Decimal("1.875")},
        ]
    }
    serialized = bs_serialize(raw_analysis)
    assert serialized["metrics"][0] == "not-a-dict-metric"
    assert serialized["metrics"][1]["value"] == 1000
    assert serialized["metrics"][2]["value"] == 1.875


# ---------------------------------------------------------------------------
# 2. White-box tests for app.analysis.bank_kpis
# ---------------------------------------------------------------------------
def test_bank_helper_conversions_and_error_branches() -> None:
    """Branch coverage for bank_kpis conversion helper functions."""
    # Boolean rejected
    with pytest.raises(InvalidOperation, match="Boolean value"):
        bank_to_decimal(True)
    with pytest.raises(InvalidOperation, match="Boolean value"):
        bank_to_decimal(False)

    # Valid Decimal passed directly
    assert bank_to_decimal(Decimal("100.50")) == Decimal("100.50")

    # Valid float conversion
    assert bank_to_decimal(250.75) == Decimal("250.75")

    # Empty string rejected
    with pytest.raises(InvalidOperation, match="Empty numeric string"):
        bank_to_decimal("    ")

    # Sign without digits rejected
    with pytest.raises(InvalidOperation, match="Sign without numeric digits"):
        bank_to_decimal("+")
    with pytest.raises(InvalidOperation, match="Sign without numeric digits"):
        bank_to_decimal("-")

    # Unsupported type rejected
    with pytest.raises(InvalidOperation, match="Unsupported type"):
        bank_to_decimal([1, 2, 3])

    # Metadata non-dict guard
    assert _get_source_metadata("not-a-dict") == (None, None)
    assert _get_source_metadata({"source_metadata": "not-a-dict"}) == (None, None)


def test_bank_kpis_structural_guards_and_serialization() -> None:
    """Branch coverage for bank KPI input validation and serialization."""
    # Non-dict inputs for opening, closing, and reconciliation (lines 575, 722, 874)
    assert calculate_opening_balance("not-a-dict")["status"] == "unavailable"
    assert calculate_closing_balance("not-a-dict")["status"] == "unavailable"
    assert calculate_balance_reconciliation("not-a-dict")["status"] == "unavailable"

    # Non-dict source_locations in closing balance (line 739)
    assert (
        calculate_closing_balance(
            {"currency": "INR", "source_locations": "not-a-dict"}
        )["status"]
        == "unavailable"
    )

    # Invalid source_row in source_locations.closing_balance (line 771)
    assert (
        calculate_closing_balance(
            {
                "currency": "INR",
                "source_locations": {"closing_balance": {"source_row": -1}},
            }
        )["status"]
        == "unavailable"
    )

    # Negative debit magnitude in calculate_total_debit (line 412)
    neg_debit_data = {"currency": "INR", "transactions": [{"debit": -50}]}
    assert calculate_total_debit(neg_debit_data)["status"] == "unavailable"

    # Transactions is not a list
    not_list_data = {"currency": "INR", "transactions": "string_not_list"}
    assert calculate_total_credit(not_list_data)["status"] == "unavailable"
    assert calculate_total_debit(not_list_data)["status"] == "unavailable"
    assert calculate_net_cash_flow(not_list_data)["status"] == "unavailable"
    assert calculate_closing_balance(not_list_data)["status"] == "unavailable"
    assert calculate_balance_reconciliation(not_list_data)["status"] == "unavailable"

    metrics = calculate_bank_kpis(
        not_list_data, include_balance_metrics=True, include_reconciliation_metric=True
    )
    assert all(m["status"] == "unavailable" for m in metrics)

    # Transactions contains non-dict element
    non_dict_tx_data = {"currency": "INR", "transactions": ["invalid_tx_string"]}
    assert calculate_total_credit(non_dict_tx_data)["status"] == "unavailable"
    assert calculate_total_debit(non_dict_tx_data)["status"] == "unavailable"
    assert calculate_net_cash_flow(non_dict_tx_data)["status"] == "unavailable"
    assert calculate_opening_balance(non_dict_tx_data)["status"] == "unavailable"
    assert calculate_closing_balance(non_dict_tx_data)["status"] == "unavailable"

    # Serialization guards (line 1165: non-dict metrics)
    assert bank_serialize("not-a-dict") == "not-a-dict"
    raw_bank_res = {
        "metrics": [
            "not-a-dict-metric",
            {"key": "total_credit", "value": Decimal("50000.00")},
            {"key": "net_cash_flow", "value": Decimal("-1250.75")},
        ]
    }
    s_res = bank_serialize(raw_bank_res)
    assert s_res["metrics"][0] == "not-a-dict-metric"
    assert s_res["metrics"][1]["value"] == 50000
    assert s_res["metrics"][2]["value"] == -1250.75
