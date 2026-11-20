"""Check exact JSON and compatibility with the existing analysis functions."""

import json
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.analysis.balance_sheet_kpis import analyze_balance_sheet
from app.analysis.bank_kpis import analyze_bank_statement
from app.schemas.analysis_responses import WorkspaceAnalysisResponse

EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "examples"
WORKSPACE_ID = UUID("3bfcd46e-3ca5-46e6-a8d2-73dc478130f6")


def read_example(name):
    return json.loads(
        (EXAMPLES / name).read_text(encoding="utf-8"), parse_float=Decimal
    )


@pytest.mark.parametrize(
    ("document", "calculate", "expected_key"),
    [
        ("bank-statement.json", analyze_bank_statement, "total_credit"),
        ("balance-sheet.json", analyze_balance_sheet, "working_capital"),
    ],
)
def test_calculator_output_matches_response_contract(document, calculate, expected_key):
    statement = read_example(document)
    response = WorkspaceAnalysisResponse.model_validate(
        calculate(statement, workspace_id=str(WORKSPACE_ID))
    )
    encoded = json.loads(response.to_wire_json(), parse_float=Decimal)
    assert encoded["workspace_id"] == str(WORKSPACE_ID)
    metric = next(item for item in encoded["metrics"] if item["key"] == expected_key)
    assert (
        metric["source_refs"][0]["document_id"]
        == statement["source_metadata"]["document_id"]
    )
    assert metric["source_refs"][0]["source_rows"]


def test_precise_numbers_zero_and_unavailable_values_on_the_wire():
    data = read_example("financial-analysis.json")
    amount = Decimal("-123456789012345.6789012345")
    data["metrics"][0]["value"] = amount
    data["metrics"][1]["value"] = 0
    data["metrics"][2].update(value=None, status="unavailable", reason="Missing input.")
    data.update(
        currency=None, reliability="insufficient_data", warnings=["Missing input."]
    )

    wire = WorkspaceAnalysisResponse.model_validate(data).to_wire_json()
    encoded = json.loads(wire, parse_float=Decimal)
    assert [metric["value"] for metric in encoded["metrics"]] == [amount, 0, None]
    assert encoded["metrics"][2]["reason"] == "Missing input."
    assert encoded["currency"] is None
    assert encoded["warnings"] == ["Missing input."]


@pytest.mark.parametrize(
    "value", [0.1, "0.1", True, Decimal("NaN"), Decimal("Infinity")]
)
def test_rejects_inexact_or_non_numeric_calculator_output(value):
    data = read_example("financial-analysis.json")
    data["metrics"][0]["value"] = value
    with pytest.raises(ValidationError):
        WorkspaceAnalysisResponse.model_validate(data)


@pytest.mark.parametrize(("status", "value"), [("available", None), ("unavailable", 0)])
def test_rejects_contradictory_metric_availability(status, value):
    data = read_example("balance-sheet-analysis.json")
    data["metrics"][0].update(status=status, value=value)
    with pytest.raises(ValidationError):
        WorkspaceAnalysisResponse.model_validate(data)
