"""Tests for financial tool schemas and execution engine."""

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.ai.tools import (
    FINANCIAL_TOOLS,
    ToolExecutionError,
    ToolResult,
    _metric_dict_to_tool_result,
    execute_tool,
)


def load_fixture(filename: str) -> dict:
    repo_root = Path(__file__).resolve().parents[3]
    fixture_path = repo_root / "contracts" / "examples" / filename
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


def test_financial_tools_schema_valid() -> None:
    assert len(FINANCIAL_TOOLS) >= 5
    for tool in FINANCIAL_TOOLS:
        assert tool["type"] == "function"
        assert "name" in tool["function"]
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]


def test_bank_total_credit() -> None:
    data = load_fixture("bank-statement.json")
    result = execute_tool("bank_total_credit", {}, data)

    assert result.name == "bank_total_credit"
    assert result.value == Decimal("5000")
    assert result.unit == "INR"
    assert result.calculation_id == "bank.total_credit.v1"
    assert result.status == "available"
    assert len(result.source_refs) == 1
    assert result.source_refs[0].source_rows == [6]


def test_bank_total_debit() -> None:
    data = load_fixture("bank-statement.json")
    result = execute_tool("bank_total_debit", {}, data)

    assert result.name == "bank_total_debit"
    assert result.value == Decimal("2500")
    assert result.unit == "INR"
    assert result.calculation_id == "bank.total_debit.v1"
    assert result.status == "available"
    assert len(result.source_refs) == 1
    assert result.source_refs[0].source_rows == [7, 8]


def test_bank_net_cash_flow() -> None:
    data = load_fixture("bank-statement.json")
    result = execute_tool("bank_net_cash_flow", {}, data)

    assert result.name == "bank_net_cash_flow"
    assert result.value == Decimal("2500")
    assert result.unit == "INR"
    assert result.calculation_id == "bank.net_cash_flow.v1"
    assert result.status == "available"
    assert len(result.source_refs) == 1
    assert result.source_refs[0].source_rows == [6, 7, 8]


def test_balance_sheet_working_capital() -> None:
    data = load_fixture("balance-sheet.json")
    result = execute_tool("balance_sheet_working_capital", {}, data)

    assert result.name == "balance_sheet_working_capital"
    # (150 current assets - 80 current liabilities) * 100,000 scale = 7,000,000
    assert result.value == Decimal("7000000")
    assert result.unit == "INR"
    assert result.calculation_id == "balance_sheet.working_capital.v1"
    assert result.status == "available"


def test_balance_sheet_verify_reconciliation() -> None:
    data = load_fixture("balance-sheet.json")
    result = execute_tool("balance_sheet_verify_reconciliation", {}, data)

    assert result.name == "balance_sheet_verify_reconciliation"
    assert result.value == Decimal("0")
    assert result.status == "available"
    assert result.calculation_id == "balance_sheet.balance_difference.v1"


def test_unknown_tool_raises_error() -> None:
    data = load_fixture("bank-statement.json")
    with pytest.raises(ToolExecutionError, match="Unknown bank statement tool"):
        execute_tool("non_existent_tool", {}, data)


def test_tool_result_decimal_precision_preserved() -> None:
    large_val = Decimal("123456789012345.6789")
    tr = ToolResult(
        name="test_tool",
        value=large_val,
        unit="INR",
        calculation_id="test.calc.v1",
    )
    serialized = tr.to_dict()
    assert serialized["value"] == "123456789012345.6789"
    assert isinstance(serialized["value"], str)


def test_bank_missing_currency_returns_unavailable() -> None:
    data = load_fixture("bank-statement.json")
    del data["currency"]
    result = execute_tool("bank_total_credit", {}, data)
    assert result.status == "unavailable"
    assert result.value is None
    assert "currency" in (result.reason or "").lower()


def test_bank_missing_closing_balance_returns_unavailable() -> None:
    data = load_fixture("bank-statement.json")
    del data["closing_balance"]
    result = execute_tool("bank_closing_balance", {}, data)
    assert result.status == "unavailable"
    assert result.value is None
    assert "closing_balance" in (result.reason or "").lower()


def test_missing_source_row_not_invented() -> None:
    data = load_fixture("bank-statement.json")
    # Remove source_row from second transaction
    del data["transactions"][1]["source_row"]
    result = execute_tool("bank_total_debit", {}, data)
    # Only transaction 2 (source_row 8) should be present; transaction 1 should not have an invented index
    assert result.source_refs[0].source_rows == [8]


def test_metric_dict_to_tool_result_adapter() -> None:
    metric = {
        "key": "total_credit",
        "value": Decimal("7500.50"),
        "unit": "INR",
        "calculation_id": "bank.total_credit.v1",
        "status": "available",
        "reason": None,
        "source_refs": [
            {
                "document_id": "doc_123",
                "sheet_name": "Sheet1",
                "source_rows": [10, 11],
                "field_paths": ["transactions[0].credit"],
            }
        ],
    }
    result = _metric_dict_to_tool_result("bank_total_credit", metric)
    assert result.name == "bank_total_credit"
    assert result.value == Decimal("7500.50")
    assert result.unit == "INR"
    assert result.calculation_id == "bank.total_credit.v1"
    assert result.status == "available"
    assert len(result.source_refs) == 1
    assert result.source_refs[0].document_id == "doc_123"
    assert result.source_refs[0].sheet_name == "Sheet1"
    assert result.source_refs[0].source_rows == [10, 11]
    assert result.source_refs[0].field_paths == ["transactions[0].credit"]


def test_bank_tool_delegates_to_analysis_module() -> None:
    data = load_fixture("bank-statement.json")
    mock_bank_kpis = MagicMock()
    mock_bank_kpis.calculate_total_credit.return_value = {
        "key": "total_credit",
        "value": Decimal("9999"),
        "unit": "INR",
        "status": "available",
        "calculation_id": "bank.total_credit.v1",
        "source_refs": [],
    }

    with patch("app.ai.tools.bank_kpis", mock_bank_kpis):
        result = execute_tool("bank_total_credit", {}, data)
        assert result.value == Decimal("9999")
        mock_bank_kpis.calculate_total_credit.assert_called_once_with(data)


def test_balance_sheet_tool_delegates_to_analysis_module() -> None:
    data = load_fixture("balance-sheet.json")
    mock_bs_kpis = MagicMock()
    mock_bs_kpis.calculate_working_capital.return_value = {
        "key": "working_capital",
        "value": Decimal("5555555"),
        "unit": "INR",
        "status": "available",
        "calculation_id": "balance_sheet.working_capital.v1",
        "source_refs": [],
    }

    with patch("app.ai.tools.balance_sheet_kpis", mock_bs_kpis):
        result = execute_tool("balance_sheet_working_capital", {}, data)
        assert result.value == Decimal("5555555")
        mock_bs_kpis.calculate_working_capital.assert_called_once_with(data)
