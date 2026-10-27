"""Tests for financial tool schemas and execution engine."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.ai.tools import FINANCIAL_TOOLS, ToolExecutionError, execute_tool


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
