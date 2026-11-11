"""Real production upload entry point and parser with synthetic Supabase HTTP."""

import csv
import io
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import httpx
import pytest
import simplejson
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.core.security import get_auth_client
from app.main import app

USER_A = "10000000-0000-4000-8000-000000000001"
USER_B = "10000000-0000-4000-8000-000000000002"
FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "parsers/fixtures/synthetic_bank_statement.csv"
)


@pytest.fixture
def real_upload():
    previous = app.dependency_overrides.copy()
    state = {"events": [], "requests": [], "parsed": [], "attempts": []}
    users = {"Bearer token-a": USER_A, "Bearer token-b": USER_B}

    def handle(request):
        token = request.headers["authorization"]
        owner = users[token]
        state["requests"].append((request.url.path, owner, token))
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": owner})
        state["events"].append(request.url.path)
        if request.url.path.endswith("/reserve_source_upload"):
            values = (
                request.json()
                if hasattr(request, "json")
                else simplejson.loads(request.content)
            )
            state["attempts"].append((owner, values))
            path = f"{owner}/{values['p_workspace_id']}/{values['p_document_id']}/source.{values['p_file_extension']}"
            return httpx.Response(
                200,
                json={
                    "workspace": {
                        "id": values["p_workspace_id"],
                        "name": values["p_name"],
                        "user_type": values["p_user_type"],
                        "document_type": values["p_document_type"],
                        "created_at": "2026-11-08T09:00:00Z",
                    },
                    "document": {
                        "id": values["p_document_id"],
                        "status": "uploaded",
                        "file_path": path,
                    },
                },
            )
        if request.url.path.startswith("/storage/v1/object/financial-documents/"):
            assert request.headers["x-upsert"] == "false"
            state["source"] = request.content
            return httpx.Response(
                200, json={"Key": request.url.path.removeprefix("/storage/v1/object/")}
            )
        assert request.url.path.endswith("/finalize_bank_statement")
        values = simplejson.loads(request.content, use_decimal=True)
        state["parsed"].append(values["p_parsed_json"])
        return httpx.Response(
            200,
            json={
                "workspace_id": values["p_workspace_id"],
                "document_id": values["p_document_id"],
                "status": "parsed",
                "transaction_count": len(values["p_parsed_json"]["transactions"]),
            },
        )

    async def connection():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handle),
        ) as upstream:
            yield upstream

    app.dependency_overrides[get_auth_client] = connection
    try:
        with TestClient(app) as client:
            yield client, state
    finally:
        app.dependency_overrides = previous


def post(client, content, *, kind="csv", token="token-a"):
    mime = (
        "text/csv"
        if kind == "csv"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return client.post(
        "/api/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"user_type": "personal", "document_type": "bank_statement"},
        files={"file": (f"statement.{kind}", content, mime)},
    )


@pytest.mark.parametrize("kind", ["csv", "xlsx"])
def test_real_parser_to_atomic_save_preserves_source_and_exact_values(
    real_upload, kind
):
    client, state = real_upload
    content = FIXTURE.read_bytes()
    if kind == "xlsx":
        book = Workbook()
        book.active.title = "Synthetic account"
        for row in csv.reader(io.StringIO(content.decode())):
            book.active.append(row)
        output = io.BytesIO()
        book.save(output)
        book.close()
        content = output.getvalue()
    response = post(client, content, kind=kind)
    assert response.status_code == 201, response.text
    document = response.json()["document"]
    UUID(document["id"])
    assert document["status"] == "parsed"
    parsed = state["parsed"][0]
    assert parsed["source_metadata"]["document_id"] == document["id"]
    assert parsed["source_metadata"]["sheet_name"] == (
        "Synthetic account" if kind == "xlsx" else None
    )
    assert [row["source_row"] for row in parsed["transactions"]] == [6, 7, 8]
    assert parsed["opening_balance"] == Decimal("10000")
    assert parsed["transactions"][0]["credit"] == Decimal("5000")
    assert state["source"] == content
    assert [path.split("/")[-1] for path in state["events"]] == [
        "reserve_source_upload",
        f"source.{kind}",
        "finalize_bank_statement",
    ]
    assert "file_path" not in response.text


@pytest.mark.parametrize(
    "content",
    [
        b"Foo,Bar\n1,2\n",
        b"Date,Description,Debit,Credit,Balance\nnot-a-date,private,0,1,1\n",
    ],
)
def test_real_parser_rejections_do_not_write_or_leak(real_upload, content):
    client, state = real_upload
    response = post(client, content)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] in {
        "statement_parse_failed",
        "invalid_parsed_document",
    }
    assert state["events"] == []
    assert "private" not in response.text


def test_real_parser_retains_high_precision_decimal_text(real_upload):
    client, state = real_upload
    content = (
        b"Date,Description,Debit,Credit,Balance\n"
        b"2026-01-01,Precise,123456789012345.6789,0,-0.1234567890123456789\n"
    )
    assert post(client, content).status_code == 201
    row = state["parsed"][0]["transactions"][0]
    assert row["debit"] == Decimal("123456789012345.6789")
    assert row["balance"] == Decimal("-0.1234567890123456789")


def test_ten_thousand_transactions_plus_metadata_are_accepted(real_upload):
    client, state = real_upload
    content = (
        b"Bank: Synthetic\nCurrency: INR\nDate,Description,Debit,Credit,Balance\n"
        + b"2026-01-01,Synthetic,0,1,1\n" * 10_000
        + b"Closing Balance: 1\n"
    )
    response = post(client, content)
    assert response.status_code == 201, response.text
    assert len(state["parsed"][0]["transactions"]) == 10_000


def test_parser_transaction_limit_blocks_before_writes(real_upload):
    client, state = real_upload
    content = (
        b"Date,Description,Debit,Credit,Balance\n"
        + b"2026-01-01,Synthetic,0,1,1\n" * 10_001
    )
    response = post(client, content)
    assert response.status_code == 422
    assert state["events"] == []


def test_users_keep_original_tokens_and_owner_context(real_upload):
    client, state = real_upload
    for token in ["token-a", "token-b", "token-a"]:
        assert post(client, FIXTURE.read_bytes(), token=token).status_code == 201
    assert [owner for owner, _ in state["attempts"]] == [USER_A, USER_B, USER_A]
    assert all(
        token == ("Bearer token-a" if owner == USER_A else "Bearer token-b")
        for _, owner, token in state["requests"]
    )
    assert len({data["p_workspace_id"] for _, data in state["attempts"]}) == 3


@pytest.mark.parametrize("date_value", ["not-a-date", "=DATE(2026,1,1)", None])
def test_bad_xlsx_transaction_dates_and_formulas_fail_before_writes(
    real_upload, date_value
):
    client, state = real_upload
    book = Workbook()
    book.active.append(["Date", "Description", "Debit", "Credit", "Balance"])
    book.active.append([date_value, "private", 0, 12, 12])
    output = io.BytesIO()
    book.save(output)
    book.close()
    response = post(client, output.getvalue(), kind="xlsx")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "statement_parse_failed"
    assert state["events"] == []
    assert "private" not in response.text


def test_upload_openapi_exposes_the_actual_multipart_fields():
    operation = app.openapi()["paths"]["/api/upload"]["post"]
    schema = operation["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert schema["required"] == ["user_type", "document_type", "file"]
    assert schema["properties"]["file"]["format"] == "binary"
