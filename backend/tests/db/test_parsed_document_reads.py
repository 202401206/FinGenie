"""Owned reads through synthetic Data API responses and real auth dependencies."""

import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from uuid import UUID

import httpx
import pytest
import simplejson
from fastapi import Depends, FastAPI

from app.core.security import get_auth_client
from app.db.dependencies import get_workspace_repository
from app.db.errors import (
    DatabaseUnauthorized,
    DatabaseUnavailable,
    DocumentNotReady,
    WorkspaceNotFound,
)
from app.db.parsed_models import ParsedBankStatement
from app.db.parsed_read_models import ParsedBalanceSheet
from app.db.repositories.workspaces import WorkspaceRepository

OWNER = UUID("10000000-0000-4000-8000-000000000001")
OTHER = UUID("10000000-0000-4000-8000-000000000002")
WORKSPACE = UUID("20000000-0000-4000-8000-000000000001")
DOCUMENT = UUID("30000000-0000-4000-8000-000000000001")


def workspace(kind="bank_statement"):
    return {
        "id": str(WORKSPACE),
        "name": "Synthetic document",
        "user_type": "business",
        "document_type": kind,
        "created_at": "2026-01-31T12:00:00Z",
    }


def document(kind="bank_statement", **changes):
    name = "bank-statement.json" if kind == "bank_statement" else "balance-sheet.json"
    fixture = Path(__file__).resolve().parents[3] / "contracts/examples" / name
    parsed = json.loads(fixture.read_text(encoding="utf-8"), parse_float=Decimal)
    parsed["source_metadata"]["document_id"] = str(DOCUMENT)
    return {
        "id": str(DOCUMENT),
        "workspace_id": str(WORKSPACE),
        "status": "parsed",
        "parsed_json": parsed,
        **changes,
    }


def response(rows):
    # json= would route Decimal through a serializer that cannot preserve it.
    return httpx.Response(200, text=simplejson.dumps(rows, use_decimal=True))


def read(handler, user=OWNER):
    async def run():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handler),
        ) as client:
            repo = WorkspaceRepository(client, user, "synthetic-token")
            return await repo.get_parsed_document(WORKSPACE)

    return asyncio.run(run())


def handler_for(rows, kind="bank_statement"):
    def handler(request):
        assert request.method == "GET"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        if request.url.path == "/rest/v1/workspaces":
            assert request.url.params["user_id"] == f"eq.{OWNER}"
            assert request.url.params["id"] == f"eq.{WORKSPACE}"
            return response([workspace(kind)])
        assert request.url.path == "/rest/v1/documents"
        assert dict(request.url.params) == {
            "select": "id,workspace_id,status,parsed_json",
            "workspace_id": f"eq.{WORKSPACE}",
        }
        return response(rows)

    return handler


@pytest.mark.parametrize("kind", ["bank_statement", "balance_sheet"])
def test_successful_owned_read_validates_type_and_preserves_exact_values(kind):
    row = document(kind)
    parsed = row["parsed_json"]
    exact = Decimal("12345678901234567890.1234567890123456789")
    negative = Decimal("-0.1234567890123456789")
    parsed["currency"] = None
    parsed["extra_detail"] = {"amount": exact, "missing": None}
    if kind == "bank_statement":
        parsed["opening_balance"] = exact
        parsed["transactions"][0].update(debit=exact, credit=0, balance=negative)
    else:
        parsed["unit_scale"] = None
        parsed["assets"]["current"][0]["value"] = exact
        parsed["equity"]["retained_earnings"] = negative
    context = read(handler_for([row], kind))
    assert context.workspace.id == WORKSPACE
    assert context.document_id == DOCUMENT
    result = context.parsed_json
    assert result.currency is None
    assert result.extra_detail == {"amount": exact, "missing": None}
    if kind == "bank_statement":
        assert isinstance(result, ParsedBankStatement)
        assert result.opening_balance == exact
        assert result.transactions[0].debit == exact
        assert result.transactions[0].credit == Decimal(0)
        assert result.transactions[0].balance == negative
        assert isinstance(result.transactions[0].debit, Decimal)
    else:
        assert isinstance(result, ParsedBalanceSheet)
        assert result.unit_scale is None
        assert result.assets.current[0].value == exact
        assert isinstance(result.assets.current[0].value, Decimal)
        assert result.equity.retained_earnings == negative


@pytest.mark.parametrize("user", [OWNER, OTHER])
def test_missing_and_foreign_workspaces_have_identical_failure_without_child_read(user):
    def handler(request):
        assert request.url.path == "/rest/v1/workspaces"
        assert request.url.params["user_id"] == f"eq.{user}"
        return response([])

    with pytest.raises(WorkspaceNotFound) as caught:
        read(handler, user)
    assert str(caught.value) == ""


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [document(status="uploaded")],
        [document(status="failed")],
        [document(parsed_json=None)],
    ],
)
def test_owned_workspace_without_a_completed_result_is_not_ready(rows):
    with pytest.raises(DocumentNotReady):
        read(handler_for(rows))


@pytest.mark.parametrize(
    "change",
    [
        {"workspace_id": str(OTHER)},
        {"id": str(OTHER)},
        {"parsed_json": {}},
        {"parsed_json": []},
        {"status": "unexpected"},
    ],
)
def test_corrupt_document_is_an_integrity_failure_not_not_ready(change):
    with pytest.raises(DatabaseUnavailable) as caught:
        read(handler_for([document(**change)]))
    assert str(caught.value) == ""


def test_multiple_documents_violate_the_single_document_contract():
    with pytest.raises(DatabaseUnavailable):
        read(handler_for([document(), document()]))


@pytest.mark.parametrize("kind", ["bank_statement", "balance_sheet"])
def test_document_type_mismatch_is_not_accepted(kind):
    other = "balance_sheet" if kind == "bank_statement" else "bank_statement"
    with pytest.raises(DatabaseUnavailable):
        read(handler_for([document(other)], kind))


@pytest.mark.parametrize("stage", ["workspaces", "documents"])
@pytest.mark.parametrize("status", [401, 403, 500])
def test_data_api_errors_are_sanitized(stage, status):
    good = handler_for([document()])

    def handler(request):
        if request.url.path == f"/rest/v1/{stage}":
            return httpx.Response(status, text="private upstream data")
        return good(request)

    error = DatabaseUnauthorized if status == 401 else DatabaseUnavailable
    with pytest.raises(error) as caught:
        read(handler)
    assert "private" not in str(caught.value)


def test_network_and_malformed_json_are_dependency_failures():
    def timeout(request):
        raise httpx.ReadTimeout("private details", request=request)

    for handler in [timeout, lambda request: httpx.Response(200, text="not JSON")]:
        with pytest.raises(DatabaseUnavailable):
            read(handler)


def test_real_dependency_pairs_verified_identity_with_original_token():
    async def run():
        app = FastAPI()
        calls = []
        users = {"Bearer token-a": OWNER, "Bearer token-b": OTHER}

        def handler(request):
            token = request.headers["authorization"]
            calls.append((request.url.path, token))
            user = users[token]
            if request.url.path == "/auth/v1/user":
                return response_user(user)
            assert request.headers["apikey"] == "sb_publishable_synthetic"
            if request.url.path == "/rest/v1/workspaces":
                assert request.url.params["user_id"] == f"eq.{user}"
                return response([workspace()] if user == OWNER else [])
            assert user == OWNER
            return response([document()])

        async def mock_client():
            async with httpx.AsyncClient(
                base_url="https://synthetic.supabase.co",
                headers={"apikey": "sb_publishable_synthetic"},
                transport=httpx.MockTransport(handler),
            ) as client:
                yield client

        app.dependency_overrides[get_auth_client] = mock_client

        @app.get("/reader-test")
        async def endpoint(
            repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
        ):
            try:
                context = await repo.get_parsed_document(WORKSPACE)
            except WorkspaceNotFound:
                return {"not_found": True}
            return {"document_id": str(context.document_id)}

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (await client.get("/reader-test")).status_code == 401
            assert calls == []
            for token in ["token-a", "token-b", "token-a"]:
                result = await client.get(
                    "/reader-test", headers={"Authorization": f"Bearer {token}"}
                )
                assert result.status_code == 200
                assert result.json() == (
                    {"not_found": True}
                    if token == "token-b"
                    else {"document_id": str(DOCUMENT)}
                )

    asyncio.run(run())


def response_user(user):
    return httpx.Response(200, json={"id": str(user)})
