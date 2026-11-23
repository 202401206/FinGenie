"""Owned dashboard API with real auth/repository code over synthetic HTTP."""

import json
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.security import get_auth_client
from app.main import app
from tests.db.test_parsed_document_reads import (
    DOCUMENT,
    OTHER,
    OWNER,
    WORKSPACE,
    document,
    response,
    workspace,
)

URL = f"/api/workspaces/{WORKSPACE}/dashboard"
HEADERS = {"Authorization": "Bearer owner"}


@pytest.fixture
def dashboard_client(monkeypatch):
    state = {"kind": "bank_statement", "rows": [document()], "reads": []}

    def handle(request):
        assert request.method == "GET"
        token = request.headers.get("authorization")
        user = {"Bearer owner": OWNER, "Bearer other": OTHER}.get(token)
        if request.url.path == "/auth/v1/user":
            return (
                httpx.Response(200, json={"id": str(user)})
                if user
                else httpx.Response(401)
            )
        assert user is not None
        state["reads"].append(request.url.path)
        if request.url.path == "/rest/v1/workspaces":
            assert request.url.params["user_id"] == f"eq.{user}"
            if user != OWNER or request.url.params["id"] != f"eq.{WORKSPACE}":
                return response([])
            return response([workspace(state["kind"])])
        assert request.url.path == "/rest/v1/documents"
        assert user == OWNER
        assert request.url.params["workspace_id"] == f"eq.{WORKSPACE}"
        if status := state.get("db_error"):
            return httpx.Response(status, text="private SQL detail")
        return response(state["rows"])

    async def connection():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            transport=httpx.MockTransport(handle),
        ) as client:
            yield client

    monkeypatch.setitem(app.dependency_overrides, get_auth_client, connection)
    with TestClient(app) as client:
        yield client, state


@pytest.mark.parametrize("kind", ["bank_statement", "balance_sheet"])
def test_dashboard_reads_owned_saved_context_and_applies_metadata(
    kind, dashboard_client
):
    client, state = dashboard_client
    state.update(kind=kind, rows=[document(kind)])
    original = deepcopy(state["rows"])
    result = client.get(URL, headers=HEADERS)
    assert result.status_code == 200, result.text
    body = json.loads(result.content, parse_float=Decimal)
    assert set(body) == {
        "workspace_id",
        "document_id",
        "document_type",
        "metadata",
        "analysis",
        "charts",
        "largest_inflows",
        "largest_outflows",
    }
    assert body["workspace_id"] == str(WORKSPACE)
    assert body["document_id"] == str(DOCUMENT)
    assert body["document_type"] == kind
    analysis = body["analysis"]
    assert analysis["workspace_id"] == str(WORKSPACE)
    assert analysis["reliability"] == "valid"
    metrics = {metric["key"]: metric for metric in analysis["metrics"]}
    assert state["rows"] == original
    assert state["reads"] == ["/rest/v1/workspaces", "/rest/v1/documents"]
    if kind == "bank_statement":
        assert body["metadata"] == {
            "company": None,
            "currency": "INR",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "reporting_date": None,
            "unit_scale": None,
        }
        assert metrics["opening_balance"]["value"] == 10000
        assert metrics["closing_balance"]["value"] == 12500
        assert metrics["average_balance"]["status"] == "available"
        assert body["largest_inflows"][0]["amount"] == 5000
        assert body["largest_outflows"][0]["amount"] == 2000
        assert {chart["key"] for chart in body["charts"]} == {
            "daily_flows",
            "monthly_flows",
            "daily_balances",
            "debit_categories",
        }
    else:
        assert body["metadata"] == {
            "company": "Synthetic Demo Company",
            "currency": "INR",
            "period_start": None,
            "period_end": None,
            "reporting_date": "2026-01-31",
            "unit_scale": 100000,
        }
        assert metrics["working_capital"]["value"] == 7_000_000
        assert metrics["debt_to_equity"]["status"] == "available"
        assert metrics["current_ratio"]["value"] == Decimal("1.875")
        assert body["largest_inflows"] == body["largest_outflows"] == []
    references = [
        ref for metric in analysis["metrics"] for ref in metric["source_refs"]
    ] + [
        ref
        for chart in body["charts"]
        for series in chart["series"]
        for point in series["points"]
        for ref in point["source_refs"]
    ]
    assert references and all(ref["document_id"] == str(DOCUMENT) for ref in references)
    for private in (
        "file_path",
        "expected_json",
        "user_id",
        "access_token",
        "parsed_json",
    ):
        assert private not in body


def test_missing_and_foreign_ids_stop_before_document_reads_and_calculation(
    dashboard_client,
):
    client, state = dashboard_client
    with patch("app.api.routes.dashboard.build_workspace_dashboard") as calculate:
        missing = client.get(
            f"/api/workspaces/{UUID(int=19)}/dashboard", headers=HEADERS
        )
        foreign = client.get(URL, headers={"Authorization": "Bearer other"})
    assert missing.status_code == foreign.status_code == 404
    assert missing.json() == foreign.json()
    assert state["reads"] == ["/rest/v1/workspaces", "/rest/v1/workspaces"]
    calculate.assert_not_called()


@pytest.mark.parametrize(
    "token", [None, "Basic invalid", "Bearer invalid", "Bearer expired"]
)
def test_missing_invalid_and_expired_auth_cannot_read_dashboard(
    dashboard_client, token
):
    client, state = dashboard_client
    headers = {} if token is None else {"Authorization": token}
    result = client.get(URL, headers=headers)
    assert result.status_code == 401
    assert result.headers["www-authenticate"] == "Bearer"
    assert state["reads"] == []


def test_invalid_uuid_is_422_before_private_reads(dashboard_client):
    client, state = dashboard_client
    result = client.get("/api/workspaces/not-a-uuid/dashboard", headers=HEADERS)
    assert result.status_code == 422
    assert state["reads"] == []


@pytest.mark.parametrize("status", ["uploaded", "failed", "absent"])
def test_dashboard_requires_parsed_document(dashboard_client, status):
    client, state = dashboard_client
    if status == "absent":
        state["rows"] = []
    else:
        state["rows"][0]["status"] = status
    result = client.get(URL, headers=HEADERS)
    assert result.status_code == 409
    assert result.json()["detail"]["code"] == "document_not_ready"


@pytest.mark.parametrize("status", [401, 503])
def test_dependency_errors_are_safe(dashboard_client, status):
    client, state = dashboard_client
    state["db_error"] = status
    result = client.get(URL, headers=HEADERS)
    assert result.status_code == status
    assert "private SQL" not in result.text
    if status == 401:
        assert result.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "kind,case",
    [
        ("bank_statement", "currency"),
        ("bank_statement", "empty"),
        ("bank_statement", "unbalanced"),
        ("balance_sheet", "currency"),
        ("balance_sheet", "unit_scale"),
        ("balance_sheet", "amount"),
        ("balance_sheet", "unbalanced"),
    ],
)
def test_input_gaps_and_unreliable_figures_return_truthful_dashboard(
    dashboard_client, kind, case
):
    client, state = dashboard_client
    state.update(kind=kind, rows=[document(kind)])
    parsed = state["rows"][0]["parsed_json"]
    if case in {"currency", "unit_scale"}:
        parsed[case] = None
    elif case == "amount":
        parsed["assets"]["current"][0]["value"] = None
    elif case == "empty":
        parsed["transactions"] = []
    elif kind == "bank_statement":
        parsed["closing_balance"] = 999
    else:
        parsed["equity"]["total"] = 179
    result = client.get(URL, headers=HEADERS)
    assert result.status_code == 200, result.text
    body = result.json()
    analysis = body["analysis"]
    assert analysis["warnings"]
    assert analysis["reliability"] == (
        "unreliable" if case in {"unbalanced", "empty"} else "insufficient_data"
    )
    metrics = {metric["key"]: metric for metric in analysis["metrics"]}
    if case in {"currency", "unit_scale"}:
        assert body["metadata"][case] is None
        assert all(chart["status"] == "unavailable" for chart in body["charts"])
    elif case == "empty":
        assert metrics["average_balance"]["value"] is None
        assert body["largest_inflows"] == body["largest_outflows"] == []
    elif case == "amount":
        assert metrics["working_capital"]["value"] is None
        assert metrics["working_capital"]["reason"]
    elif kind == "bank_statement":
        assert metrics["average_balance"]["value"] is None
    else:
        assert metrics["balance_difference"]["value"] == 100_000


def test_dashboard_uses_all_saved_transactions_and_preserves_legitimate_zero(
    dashboard_client,
):
    client, state = dashboard_client
    parsed = state["rows"][0]["parsed_json"]
    start = date(2026, 1, 1)
    parsed.update(
        opening_balance=Decimal(0),
        closing_balance=Decimal(60),
        period_start=start.isoformat(),
        period_end=(start + timedelta(days=59)).isoformat(),
        transactions=[
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "description": "Synthetic credit",
                "debit": 0,
                "credit": 1,
                "balance": index + 1,
                "source_row": index + 6,
            }
            for index in range(60)
        ],
    )
    response = client.get(URL, headers=HEADERS)
    assert response.status_code == 200, response.text
    result = response.json()
    metrics = {metric["key"]: metric for metric in result["analysis"]["metrics"]}
    assert metrics["total_credit"]["value"] == 60
    assert metrics["opening_balance"]["value"] == metrics["total_debit"]["value"] == 0
    assert metrics["average_balance"]["value"] == 30.5
    daily = next(chart for chart in result["charts"] if chart["key"] == "daily_flows")
    assert len(daily["series"][0]["points"]) == 60
    assert state["reads"] == ["/rest/v1/workspaces", "/rest/v1/documents"]


def test_dashboard_serializes_large_fractional_numbers_without_float_rounding(
    dashboard_client,
):
    client, state = dashboard_client
    parsed = state["rows"][0]["parsed_json"]
    amount = Decimal("123456789012345678901234567890.123456789")
    parsed["transactions"][0]["credit"] = amount
    result = client.get(URL, headers=HEADERS)
    assert result.status_code == 200, result.text
    assert b"123456789012345678901234567890.123456789" in result.content
    assert b'"amount":"123456789' not in result.content
    data = json.loads(result.content, parse_float=Decimal)
    assert (
        next(
            metric
            for metric in data["analysis"]["metrics"]
            if metric["key"] == "total_credit"
        )["value"]
        == amount
    )
    assert data["largest_inflows"][0]["amount"] == amount
    monthly = next(chart for chart in data["charts"] if chart["key"] == "monthly_flows")
    assert monthly["series"][0]["points"][0]["value"] == amount


@pytest.mark.parametrize("bad", ["float", "no_reason", "wrong_source", "private_field"])
def test_invalid_calculation_output_is_rejected_before_serialization(
    dashboard_client, bad
):
    client, _ = dashboard_client
    from app.services.workspace_dashboard import bank_dashboard_metrics

    def invalid(statement):
        result = bank_dashboard_metrics(statement)
        point = result["charts"][0]["series"][0]["points"][0]
        if bad == "float":
            point["value"] = 0.1
        elif bad == "no_reason":
            point.update(value=None, reason=None)
        elif bad == "wrong_source":
            point["source_refs"][0]["document_id"] = str(UUID(int=99))
        else:
            point["private_path"] = "private/synthetic.csv"
        return result

    with patch(
        "app.services.workspace_dashboard.bank_dashboard_metrics", side_effect=invalid
    ):
        result = client.get(URL, headers=HEADERS)
    assert result.status_code == 503
    assert result.json()["detail"]["code"] == "dashboard_unavailable"
    assert "private/synthetic.csv" not in result.text


def test_openapi_describes_dashboard_numbers_nulls_and_auth():
    spec = app.openapi()
    operation = spec["paths"]["/api/workspaces/{workspace_id}/dashboard"]["get"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert {"200", "401", "404", "409", "422", "503"} <= set(operation["responses"])
    schemas = spec["components"]["schemas"]
    assert schemas["DashboardPoint"]["properties"]["value"]["anyOf"] == [
        {"type": "number"},
        {"type": "null"},
    ]
    assert schemas["DashboardEntry"]["properties"]["amount"]["type"] == "number"
    assert schemas["WorkspaceDashboardResponse"]["additionalProperties"] is False
