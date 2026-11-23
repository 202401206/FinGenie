"""Analysis route and real owned-document reader over synthetic Supabase HTTP."""

import json
from decimal import Decimal
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

URL = f"/api/workspaces/{WORKSPACE}/analysis"
OWNER_HEADERS = {"Authorization": "Bearer owner"}
OTHER_HEADERS = {"Authorization": "Bearer other"}


@pytest.fixture
def analysis_client(monkeypatch):
    state = {
        "kind": "bank_statement",
        "rows": [document()],
        "reads": [],
    }

    def handle(request):
        user = {"Bearer owner": OWNER, "Bearer other": OTHER}[
            request.headers["authorization"]
        ]
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": str(user)})
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


def test_bank_analysis_keeps_real_ids_and_exact_json_values(analysis_client):
    client, state = analysis_client
    data = state["rows"][0]["parsed_json"]
    amount = Decimal("123456789012345.6789012345")
    data["transactions"][0]["credit"] = amount
    result = client.get(URL, headers=OWNER_HEADERS)
    assert result.status_code == 200, result.text
    payload = json.loads(result.content, parse_float=Decimal)
    assert payload["workspace_id"] == str(WORKSPACE)
    assert payload["document_type"] == "bank_statement"
    assert payload["reliability"] == "unreliable"
    assert payload["warnings"]
    metric = next(item for item in payload["metrics"] if item["key"] == "total_credit")
    assert metric["value"] == amount
    assert metric["source_refs"][0]["document_id"] == str(DOCUMENT)
    assert metric["source_refs"][0]["source_rows"] == [6]


def test_missing_or_foreign_workspace_does_not_read_document(analysis_client):
    client, state = analysis_client
    absent = client.get(
        f"/api/workspaces/{UUID(int=8)}/analysis", headers=OWNER_HEADERS
    )
    foreign = client.get(URL, headers=OTHER_HEADERS)
    assert absent.status_code == foreign.status_code == 404
    assert absent.json() == foreign.json()
    assert state["reads"] == ["/rest/v1/workspaces"] * 2


def test_bank_analysis_with_missing_currency_reports_unavailable_metrics(
    analysis_client,
):
    client, state = analysis_client
    state["rows"][0]["parsed_json"]["currency"] = None
    response = client.get(URL, headers=OWNER_HEADERS)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["currency"] is None
    assert result["reliability"] == "insufficient_data"
    assert all(metric["unit"] == "unknown" for metric in result["metrics"])
    assert all(metric["status"] == "unavailable" for metric in result["metrics"])


def test_authentication_and_uuid_validation_precede_database_reads(analysis_client):
    client, state = analysis_client
    assert client.get(URL).status_code == 401
    assert (
        client.get(
            "/api/workspaces/not-uuid/analysis", headers=OWNER_HEADERS
        ).status_code
        == 422
    )
    assert state["reads"] == []


@pytest.mark.parametrize("status", ["uploaded", "failed"])
def test_document_not_ready(analysis_client, status):
    client, state = analysis_client
    state["rows"][0]["status"] = status
    result = client.get(URL, headers=OWNER_HEADERS)
    assert result.status_code == 409
    assert result.json()["detail"]["code"] == "document_not_ready"


@pytest.mark.parametrize("status", [401, 503])
def test_database_failures_have_safe_errors(analysis_client, status):
    client, state = analysis_client
    state["db_error"] = status
    result = client.get(URL, headers=OWNER_HEADERS)
    assert result.status_code == status
    assert "private SQL" not in result.text
    if status == 401:
        assert result.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    ("case", "unavailable", "reliability"),
    [
        ("complete", set(), "valid"),
        (
            "currency",
            {"working_capital", "current_ratio", "balance_difference"},
            "insufficient_data",
        ),
        (
            "unit_scale",
            {"working_capital", "current_ratio", "balance_difference"},
            "insufficient_data",
        ),
        ("amount", {"working_capital", "current_ratio"}, "insufficient_data"),
        ("classification", {"working_capital", "current_ratio"}, "insufficient_data"),
        ("unmapped", {"working_capital", "current_ratio"}, "insufficient_data"),
        ("zero", {"current_ratio"}, "valid"),
        ("unbalanced", set(), "unreliable"),
    ],
)
def test_balance_analysis_readiness(analysis_client, case, unavailable, reliability):
    client, state = analysis_client
    state.update(kind="balance_sheet", rows=[document("balance_sheet")])
    data = state["rows"][0]["parsed_json"]
    if case in {"currency", "unit_scale"}:
        data[case] = None
    elif case == "amount":
        data["assets"]["current"][0]["value"] = None
    elif case == "classification":
        data["assets"]["current"][0]["canonical_field"] = None
    elif case == "unmapped":
        data["unmapped"] = [{"raw_label": "Unknown line", "source_row": 21}]
    elif case == "zero":
        data["liabilities"]["current"][0]["value"] = 0
    elif case == "unbalanced":
        data["equity"]["total"] = 179

    result = client.get(URL, headers=OWNER_HEADERS)
    assert result.status_code == 200, result.text
    payload = json.loads(result.content, parse_float=Decimal)
    assert payload["reliability"] == reliability
    metrics = {metric["key"]: metric for metric in payload["metrics"]}
    assert {
        key for key, metric in metrics.items() if metric["status"] == "unavailable"
    } == unavailable
    for key in unavailable:
        assert metrics[key]["value"] is None
        assert metrics[key]["reason"]
    if case == "complete":
        assert metrics["working_capital"]["value"] == 7_000_000
        assert metrics["current_ratio"]["value"] == Decimal("1.875")
        assert metrics["balance_difference"]["value"] == 0
    elif case == "unbalanced":
        assert metrics["balance_difference"]["value"] == 100_000
        assert payload["warnings"]
