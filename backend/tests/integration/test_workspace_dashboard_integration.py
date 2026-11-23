"""Dashboard responses through real upload parsers, repositories and local SQL/RLS."""

from copy import deepcopy
from decimal import Decimal
from uuid import uuid4

import pytest
import simplejson

from tests.integration.test_persistence_recovery import (
    ROOT,
    layout_bytes,
    statement_upload,
)
from tests.integration.test_persistence_recovery import (
    api_database_client as api_database_client,
)
from tests.integration.test_persistence_recovery import database as database
from tests.source_fixtures import OWNER

HEADERS = {"Authorization": "Bearer token-a"}
OTHER_HEADERS = {"Authorization": "Bearer token-b"}


def financial_snapshot(server, workspace_id):
    result = server.query(
        """
        select jsonb_build_object(
            'workspace', (select to_jsonb(w) from public.workspaces w where id=$1::uuid),
            'documents', (select jsonb_agg(d order by d.id) from public.documents d
                          where workspace_id=$1::uuid),
            'transactions', (select jsonb_agg(t order by t.id) from public.transactions t
                             where document_id in (
                                 select id from public.documents where workspace_id=$1::uuid
                             )),
            'attempts', (select jsonb_agg(a order by a.id) from public.upload_attempts a
                         where workspace_id=$1::uuid)
        )::text as state
        """,
        [workspace_id],
        OWNER,
    )
    assert "error" not in result
    return result["rows"][0]["state"]


@pytest.mark.parametrize("document_type", ["bank_statement", "balance_sheet"])
@pytest.mark.parametrize("layout", ["a", "b"])
@pytest.mark.parametrize("kind", ["csv", "xlsx"])
def test_uploaded_dashboard_matches_saved_data_and_reading_does_not_write(
    api_database_client, monkeypatch, document_type, layout, kind
):
    client, server = api_database_client
    content = layout_bytes(layout, kind, document_type=document_type)
    uploaded = statement_upload(
        client, content, kind, user_type="business", document_type=document_type
    )
    assert uploaded.status_code == 201, uploaded.text
    workspace_id = uploaded.json()["workspace"]["id"]
    document_id = uploaded.json()["document"]["id"]
    url = f"/api/workspaces/{workspace_id}/dashboard"
    before = financial_snapshot(server, workspace_id)
    files_before = deepcopy(server.files)
    calls = []
    handle = server.handle

    def record(request):
        calls.append((request.method, request.url.path))
        return handle(request)

    monkeypatch.setattr(server, "handle", record)
    first = client.get(url, headers=HEADERS)
    repeated = client.get(url, headers=HEADERS)
    assert first.status_code == repeated.status_code == 200, first.text
    assert repeated.content == first.content
    body = simplejson.loads(first.content, use_decimal=True)
    assert body["workspace_id"] == workspace_id
    assert body["document_id"] == document_id
    assert body["analysis"]["reliability"] == "valid"
    metrics = {item["key"]: item for item in body["analysis"]["metrics"]}
    if document_type == "bank_statement":
        assert metrics["total_credit"]["value"] == (5000 if layout == "a" else 15000)
        assert metrics["net_cash_flow"]["value"] == (2500 if layout == "a" else 11000)
        assert metrics["average_balance"]["status"] == "available"
        assert body["metadata"]["period_start"] == "2026-01-01"
        assert body["metadata"]["reporting_date"] is None
        assert body["largest_inflows"][0]["source_refs"][0]["source_rows"] == [6]
    else:
        assert metrics["working_capital"]["value"] == (
            7_000_000 if layout == "a" else 400_000_000
        )
        assert metrics["debt_to_equity"]["status"] == "available"
        assert body["metadata"]["unit_scale"] == (100000 if layout == "a" else 1000000)
        assert (
            body["metadata"]["period_start"] is body["metadata"]["period_end"] is None
        )
        assert body["metadata"]["reporting_date"] == (
            "2026-01-31" if layout == "a" else "2026-03-31"
        )
        assert body["largest_inflows"] == body["largest_outflows"] == []
    refs = [
        ref
        for chart in body["charts"]
        for series in chart["series"]
        for point in series["points"]
        for ref in point["source_refs"]
    ]
    assert refs
    assert all(ref["document_id"] == document_id for ref in refs)
    assert all(
        ref["sheet_name"] == ("Synthetic account" if kind == "xlsx" else None)
        for ref in refs
    )
    assert all(row > 0 for ref in refs for row in ref["source_rows"])
    assert "parsed_json" not in body and "file_path" not in body
    foreign = client.get(url, headers=OTHER_HEADERS)
    missing = client.get(f"/api/workspaces/{uuid4()}/dashboard", headers=HEADERS)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()
    assert all(method == "GET" for method, _ in calls)
    assert sum(path == "/rest/v1/documents" for _, path in calls) == 2
    assert financial_snapshot(server, workspace_id) == before
    assert server.files == files_before and content in server.files.values()

    if kind == "csv" and layout == "a":
        name = (
            "bank-dashboard.json"
            if document_type == "bank_statement"
            else "balance-sheet-dashboard.json"
        )
        example = simplejson.loads(
            (ROOT / "contracts/examples" / name).read_bytes(), use_decimal=True
        )
        normalized = first.content.decode().replace(
            workspace_id, example["workspace_id"]
        )
        normalized = normalized.replace(document_id, example["document_id"])
        assert simplejson.loads(normalized, use_decimal=True) == example


@pytest.mark.parametrize(
    "document_type,old,new,reliability,unavailable",
    [
        (
            "bank_statement",
            b"Currency: INR,",
            b"",
            "insufficient_data",
            "average_balance",
        ),
        (
            "bank_statement",
            b"Closing Balance: 12500",
            b"Closing Balance: 12900",
            "unreliable",
            "average_balance",
        ),
        (
            "balance_sheet",
            b"Currency: INR,Scale: Lakhs",
            b"",
            "insufficient_data",
            "debt_to_equity",
        ),
        (
            "balance_sheet",
            b"Receivables,50",
            b"Receivables,",
            "insufficient_data",
            "working_capital",
        ),
        ("balance_sheet", b"Total Equity,180", b"Total Equity,179", "unreliable", None),
    ],
)
def test_real_metadata_gaps_and_unreconciled_figures_remain_visible(
    api_database_client, document_type, old, new, reliability, unavailable
):
    client, server = api_database_client
    content = layout_bytes("a", "csv", document_type=document_type)
    assert old in content
    content = content.replace(old, new, 1)
    uploaded = statement_upload(
        client, content, user_type="business", document_type=document_type
    )
    assert uploaded.status_code == 201, uploaded.text
    workspace_id = uploaded.json()["workspace"]["id"]
    before = financial_snapshot(server, workspace_id)
    response = client.get(f"/api/workspaces/{workspace_id}/dashboard", headers=HEADERS)
    assert response.status_code == 200, response.text
    result = simplejson.loads(response.content, use_decimal=True)
    assert result["analysis"]["reliability"] == reliability
    assert result["analysis"]["warnings"]
    metrics = {metric["key"]: metric for metric in result["analysis"]["metrics"]}
    if unavailable:
        assert metrics[unavailable]["value"] is None
        assert metrics[unavailable]["reason"]
    else:
        assert metrics["balance_difference"]["value"] == 100_000
        totals = next(
            chart for chart in result["charts"] if chart["key"] == "reported_totals"
        )
        assert totals["series"][0]["points"][2]["value"] == 17_900_000
    if old.startswith(b"Currency:"):
        assert result["metadata"]["currency"] is None
        assert all(chart["status"] == "unavailable" for chart in result["charts"])
    assert financial_snapshot(server, workspace_id) == before
    assert list(server.files.values()) == [content]


@pytest.mark.parametrize("document_type", ["bank_statement", "balance_sheet"])
def test_exact_reported_decimal_survives_parser_storage_and_dashboard(
    api_database_client, document_type
):
    client, server = api_database_client
    exact = "100000000000000.123456789"
    if document_type == "bank_statement":
        content = (
            "Currency: INR,Period: 2026-01-01 to 2026-01-31\n"
            "Opening Balance: 0\nDate,Description,Debit,Credit,Balance\n"
            f"2026-01-01,Synthetic precise credit,0,{exact},{exact}\n"
            f"Closing Balance: {exact}\n"
        ).encode()
    else:
        content = layout_bytes("a", "csv", document_type=document_type)
        content = content.replace(b"Cash,100", f"Cash,{exact}".encode())
        assets = Decimal(exact) + 200
        equity = assets - 120
        content = content.replace(
            b"Total Assets,300", f"Total Assets,{assets}".encode()
        )
        content = content.replace(
            b"Total Equity,180", f"Total Equity,{equity}".encode()
        )
    uploaded = statement_upload(
        client, content, user_type="business", document_type=document_type
    )
    assert uploaded.status_code == 201, uploaded.text
    workspace_id = uploaded.json()["workspace"]["id"]
    document_id = uploaded.json()["document"]["id"]
    saved = server.query(
        "select parsed_json::text as parsed from public.documents where id=$1::uuid",
        [document_id],
        OWNER,
    )["rows"][0]
    parsed = simplejson.loads(saved["parsed"], use_decimal=True)
    response = client.get(f"/api/workspaces/{workspace_id}/dashboard", headers=HEADERS)
    assert response.status_code == 200, response.text
    result = simplejson.loads(response.content, use_decimal=True)
    if document_type == "bank_statement":
        assert parsed["transactions"][0]["credit"] == Decimal(exact)
        assert exact.encode() in response.content
        metrics = {metric["key"]: metric for metric in result["analysis"]["metrics"]}
        assert metrics["total_credit"]["value"] == Decimal(exact)
        assert metrics["average_balance"]["value"] == Decimal(exact)
        assert result["largest_inflows"][0]["amount"] == Decimal(exact)
    else:
        assert parsed["assets"]["current"][0]["value"] == Decimal(exact)
        assert parsed["unit_scale"] == 100000
        chart = next(
            chart for chart in result["charts"] if chart["key"] == "balance_components"
        )
        expected = (Decimal(exact) + 50) * 100000
        assert chart["series"][0]["points"][0]["value"] == expected
        assert str(expected).encode() in response.content
        assert result["analysis"]["reliability"] == "valid"
    assert list(server.files.values()) == [content]


@pytest.mark.parametrize("document_type", ["bank_statement", "balance_sheet"])
def test_failed_upload_dashboard_stays_unready_until_original_attempt_is_cleaned(
    api_database_client, document_type
):
    client, server = api_database_client
    server.reject_save = server.reject_delete = True
    response = statement_upload(
        client,
        layout_bytes("a", "csv", document_type=document_type),
        user_type="business",
        document_type=document_type,
    )
    assert response.status_code == 503
    attempt_id = response.json()["detail"]["attempt_id"]
    detail = client.get(f"/api/upload-attempts/{attempt_id}", headers=HEADERS)
    workspace_id = detail.json()["workspace_id"]
    assert detail.json()["status"] == "pending"
    before = financial_snapshot(server, workspace_id)
    url = f"/api/workspaces/{workspace_id}/dashboard"
    response = client.get(url, headers=HEADERS)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "document_not_ready"
    assert financial_snapshot(server, workspace_id) == before and server.files
    server.reject_delete = False
    recovery = client.post(
        f"/api/upload-attempts/{attempt_id}/recover", headers=HEADERS, json={}
    )
    assert recovery.status_code == 200 and recovery.json()["status"] == "cleaned"
    assert client.get(url, headers=HEADERS).status_code == 404
    assert not server.files
