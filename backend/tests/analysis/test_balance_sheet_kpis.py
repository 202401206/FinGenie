"""Unit and contract tests for Balance Sheet Analytics (Aarushi's Track)."""

import json
from decimal import Decimal
from pathlib import Path

from app.analysis.balance_sheet_kpis import (
    CALCULATION_ID_BALANCE_DIFFERENCE,
    CALCULATION_ID_CURRENT_RATIO,
    CALCULATION_ID_WORKING_CAPITAL,
    STATUS_AVAILABLE,
    STATUS_UNAVAILABLE,
    analyze_balance_sheet,
    calculate_balance_difference,
    calculate_current_ratio,
    calculate_working_capital,
    serialize_analysis_result,
)


def load_fixture(filename: str) -> dict:
    repo_root = Path(__file__).resolve().parents[3]
    fixture_path = repo_root / "contracts" / "examples" / filename
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


def test_working_capital_contract_fixture() -> None:
    data = load_fixture("balance-sheet.json")
    result = calculate_working_capital(data)

    assert result["status"] == STATUS_AVAILABLE
    assert result["calculation_id"] == CALCULATION_ID_WORKING_CAPITAL
    assert result["unit"] == "INR"
    assert result["value"] == Decimal("7000000")  # (150 - 80) * 100000

    ref = result["source_refs"][0]
    assert ref["document_id"] == "10000000-0000-4000-8000-000000000002"
    assert ref["sheet_name"] == "Balance Sheet"
    assert ref["source_rows"] == [3, 6, 7, 12]
    assert ref["field_paths"] == [
        "unit_scale",
        "assets.current[0].value",
        "assets.current[1].value",
        "liabilities.current[0].value",
    ]


def test_balance_difference_contract_fixture() -> None:
    data = load_fixture("balance-sheet.json")
    result = calculate_balance_difference(data)

    assert result["status"] == STATUS_AVAILABLE
    assert result["calculation_id"] == CALCULATION_ID_BALANCE_DIFFERENCE
    assert result["unit"] == "INR"
    assert result["value"] == Decimal("0")  # 300 - (120 + 180) = 0

    ref = result["source_refs"][0]
    assert ref["document_id"] == "10000000-0000-4000-8000-000000000002"
    assert ref["sheet_name"] == "Balance Sheet"
    assert ref["source_rows"] == [3, 10, 16, 20]
    assert ref["field_paths"] == [
        "unit_scale",
        "assets.total",
        "liabilities.total",
        "equity.total",
    ]


def test_current_ratio_contract_fixture() -> None:
    data = load_fixture("balance-sheet.json")
    result = calculate_current_ratio(data)

    assert result["status"] == STATUS_AVAILABLE
    assert result["calculation_id"] == CALCULATION_ID_CURRENT_RATIO
    assert result["unit"] == "ratio"
    assert result["value"] == Decimal("150") / Decimal("80")  # 1.875

    ref = result["source_refs"][0]
    assert ref["source_rows"] == [6, 7, 12]
    assert ref["field_paths"] == [
        "assets.current[0].value",
        "assets.current[1].value",
        "liabilities.current[0].value",
    ]


def test_current_ratio_zero_division_guard() -> None:
    data = {
        "currency": "INR",
        "unit_scale": 1,
        "assets": {"current": [{"value": 100, "source_row": 5}]},
        "liabilities": {"current": []},
    }
    result = calculate_current_ratio(data)
    assert result["status"] == STATUS_UNAVAILABLE
    assert result["value"] is None
    assert "division by zero" in result["reason"]


def test_analyze_balance_sheet_full_contract_envelope() -> None:
    data = load_fixture("balance-sheet.json")
    expected = load_fixture("balance-sheet-analysis.json")

    analysis = analyze_balance_sheet(data, workspace_id=expected["workspace_id"])

    assert analysis["workspace_id"] == expected["workspace_id"]
    assert analysis["document_type"] == "balance_sheet"
    assert analysis["currency"] == "INR"
    assert analysis["reliability"] == "valid"
    assert len(analysis["warnings"]) == 0

    metric_keys = [m["key"] for m in analysis["metrics"]]
    assert "working_capital" in metric_keys
    assert "balance_difference" in metric_keys

    metrics_by_key = {m["key"]: m for m in analysis["metrics"]}
    assert metrics_by_key["working_capital"]["value"] == Decimal("7000000")
    assert metrics_by_key["balance_difference"]["value"] == Decimal("0")


def test_balance_sheet_various_unit_scales() -> None:
    """Verifies unit scale multiplication across thousands, lakhs, and crores."""
    base_data = {
        "currency": "INR",
        "assets": {"current": [{"value": "10.5", "source_row": 5}]},
        "liabilities": {"current": [{"value": "5.5", "source_row": 10}]},
    }

    # Scale 1 (units)
    data_units = {**base_data, "unit_scale": 1}
    wc_units = calculate_working_capital(data_units)
    assert wc_units["value"] == Decimal("5.0")

    # Scale 1,000 (thousands)
    data_thousands = {**base_data, "unit_scale": "1,000"}
    wc_thousands = calculate_working_capital(data_thousands)
    assert wc_thousands["value"] == Decimal("5000.0")

    # Scale 10,000,000 (crores)
    data_crores = {**base_data, "unit_scale": 10000000}
    wc_crores = calculate_working_capital(data_crores)
    assert wc_crores["value"] == Decimal("50000000.0")


def test_unbalanced_balance_sheet_triggers_unreliable_warning() -> None:
    data = {
        "currency": "INR",
        "unit_scale": 1,
        "assets": {"total": 350, "current": []},
        "liabilities": {"total": 120, "current": []},
        "equity": {"total": 180},
    }
    diff = calculate_balance_difference(data)
    assert diff["value"] == Decimal("50")  # 350 - 300 = 50

    analysis = analyze_balance_sheet(data)
    assert analysis["reliability"] == "unreliable"
    assert any("reconciliation failed" in w for w in analysis["warnings"])


def test_missing_currency_triggers_unreliable() -> None:
    data = load_fixture("balance-sheet.json")
    del data["currency"]

    analysis = analyze_balance_sheet(data)
    assert analysis["reliability"] == "unreliable"
    assert analysis["currency"] == "unknown"
    assert len(analysis["warnings"]) > 0


def test_missing_unit_scale_triggers_insufficient_data() -> None:
    data = load_fixture("balance-sheet.json")
    del data["unit_scale"]

    wc = calculate_working_capital(data)
    assert wc["status"] == STATUS_UNAVAILABLE

    analysis = analyze_balance_sheet(data)
    assert analysis["reliability"] == "insufficient_data"


def test_defensive_type_checks_dirty_corrupt_data() -> None:
    corrupt_data = {
        "currency": "INR",
        "unit_scale": "100",
        "assets": {
            "current": [
                None,
                "not_a_dict",
                {"value": "1,500.50", "source_row": 5},
                {"value": None, "source_row": 6},
            ]
        },
        "liabilities": {
            "current": [
                {"value": "500", "source_row": 12},
                12345,
            ]
        },
    }
    wc = calculate_working_capital(corrupt_data)
    assert wc["status"] == STATUS_AVAILABLE
    assert wc["value"] == (Decimal("1500.50") - Decimal("500")) * Decimal("100")


def test_serialize_balance_sheet_analysis_result() -> None:
    data = load_fixture("balance-sheet.json")
    analysis = analyze_balance_sheet(data)

    serialized = serialize_analysis_result(analysis)
    for m in serialized["metrics"]:
        assert isinstance(m["value"], (int, float))

    dumped = json.dumps(serialized)
    assert isinstance(dumped, str)
    loaded = json.loads(dumped)
    assert loaded["metrics"][0]["value"] == 7000000
    assert loaded["metrics"][1]["value"] == 0
