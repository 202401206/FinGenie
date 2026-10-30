"""Unit and contract tests for Bank Statement Analytics (Aarushi's Track)."""

import json
from decimal import Decimal
from pathlib import Path

from app.analysis.bank_kpis import (
    calculate_bank_analysis,
    calculate_net_cash_flow,
    calculate_total_credit,
    calculate_total_debit,
    get_closing_balance,
    get_closing_balance_source_refs,
    get_net_cash_flow_source_refs,
    get_opening_balance,
    get_total_credit_source_refs,
    get_total_debit_source_refs,
)


def load_fixture(filename: str) -> dict:
    repo_root = Path(__file__).resolve().parents[3]
    fixture_path = repo_root / "contracts" / "examples" / filename
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


def test_calculate_total_credit_fixture() -> None:
    data = load_fixture("bank-statement.json")
    result = calculate_total_credit(data)
    assert result == Decimal("5000")
    assert isinstance(result, Decimal)


def test_calculate_total_debit_fixture() -> None:
    data = load_fixture("bank-statement.json")
    result = calculate_total_debit(data)
    assert result == Decimal("2500")
    assert isinstance(result, Decimal)


def test_calculate_net_cash_flow_fixture() -> None:
    data = load_fixture("bank-statement.json")
    result = calculate_net_cash_flow(data)
    assert result == Decimal("2500")
    assert isinstance(result, Decimal)


def test_get_closing_balance_fixture() -> None:
    data = load_fixture("bank-statement.json")
    result = get_closing_balance(data)
    assert result == Decimal("12500")
    assert isinstance(result, Decimal)


def test_get_opening_balance_fixture() -> None:
    data = load_fixture("bank-statement.json")
    result = get_opening_balance(data)
    assert result == Decimal("10000")
    assert isinstance(result, Decimal)


def test_decimal_precision_no_float_drift() -> None:
    """Verifies that fractional cents are computed with exact Decimal precision."""
    data = {
        "transactions": [
            {"credit": "0.10", "debit": 0, "source_row": 10},
            {"credit": "0.20", "debit": 0, "source_row": 11},
            {"credit": 0, "debit": "0.05", "source_row": 12},
        ]
    }
    total_credit = calculate_total_credit(data)
    total_debit = calculate_total_debit(data)
    net_flow = calculate_net_cash_flow(data)

    assert total_credit == Decimal("0.30")
    assert total_debit == Decimal("0.05")
    assert net_flow == Decimal("0.25")


def test_empty_statement_returns_zeros_and_none() -> None:
    data: dict = {}
    assert calculate_total_credit(data) == Decimal("0")
    assert calculate_total_debit(data) == Decimal("0")
    assert calculate_net_cash_flow(data) == Decimal("0")
    assert get_closing_balance(data) is None
    assert get_opening_balance(data) is None


def test_missing_or_none_fields_in_transactions() -> None:
    data = {
        "transactions": [
            {"credit": None, "debit": None, "source_row": 5},
            {"credit": "", "debit": "not_a_number", "source_row": 6},
            {"credit": 1500, "debit": 0, "source_row": 7},
        ]
    }
    assert calculate_total_credit(data) == Decimal("1500")
    assert calculate_total_debit(data) == Decimal("0")
    assert calculate_net_cash_flow(data) == Decimal("1500")


def test_source_rows_traceability_credit() -> None:
    data = load_fixture("bank-statement.json")
    refs = get_total_credit_source_refs(data)
    assert len(refs) == 1
    assert refs[0]["document_id"] == "10000000-0000-4000-8000-000000000001"
    assert refs[0]["sheet_name"] is None
    assert refs[0]["source_rows"] == [6]
    assert refs[0]["field_paths"] == ["transactions[0].credit"]


def test_source_rows_traceability_debit() -> None:
    data = load_fixture("bank-statement.json")
    refs = get_total_debit_source_refs(data)
    assert len(refs) == 1
    assert refs[0]["source_rows"] == [7, 8]
    assert refs[0]["field_paths"] == [
        "transactions[1].debit",
        "transactions[2].debit",
    ]


def test_source_rows_traceability_net_cash_flow() -> None:
    data = load_fixture("bank-statement.json")
    refs = get_net_cash_flow_source_refs(data)
    assert len(refs) == 1
    assert refs[0]["source_rows"] == [6, 7, 8]
    assert refs[0]["field_paths"] == [
        "transactions[0].credit",
        "transactions[1].debit",
        "transactions[2].debit",
    ]


def test_source_rows_closing_balance() -> None:
    data = load_fixture("bank-statement.json")
    refs = get_closing_balance_source_refs(data)
    assert len(refs) == 1
    assert refs[0]["source_rows"] == [9]
    assert refs[0]["field_paths"] == ["closing_balance"]


def test_calculate_bank_analysis_full_contract_envelope() -> None:
    data = load_fixture("bank-statement.json")
    expected = load_fixture("financial-analysis.json")

    analysis = calculate_bank_analysis(data, workspace_id=expected["workspace_id"])

    assert analysis["workspace_id"] == expected["workspace_id"]
    assert analysis["document_type"] == "bank_statement"
    assert analysis["currency"] == "INR"
    assert analysis["reliability"] == "valid"
    assert len(analysis["warnings"]) == 0

    metric_keys = [m["key"] for m in analysis["metrics"]]
    assert "total_credit" in metric_keys
    assert "total_debit" in metric_keys
    assert "net_cash_flow" in metric_keys
    assert "closing_balance" in metric_keys

    # Check metric values
    metrics_by_key = {m["key"]: m for m in analysis["metrics"]}
    assert metrics_by_key["total_credit"]["value"] == Decimal("5000")
    assert metrics_by_key["total_debit"]["value"] == Decimal("2500")
    assert metrics_by_key["net_cash_flow"]["value"] == Decimal("2500")
    assert metrics_by_key["closing_balance"]["value"] == Decimal("12500")


def test_unreliable_analysis_when_currency_missing() -> None:
    data = load_fixture("bank-statement.json")
    del data["currency"]
    analysis = calculate_bank_analysis(data)
    assert analysis["reliability"] == "unreliable"
    assert len(analysis["warnings"]) > 0
