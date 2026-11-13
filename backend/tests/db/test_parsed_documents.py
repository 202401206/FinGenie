"""Parsed-save request validation, exact JSON and safe write failures."""

import asyncio
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_auth_client, require_user
from app.db.dependencies import get_parsed_document_repository
from app.db.errors import UnsupportedDocumentType, WorkspaceNotFound
from app.db.repositories.parsed_documents import ParsedDocumentRepository
from app.schemas.responses import CurrentUser
from app.services.source_errors import (
    ParsedDocumentRejected,
    SourceConflict,
    SourceOutcomeUnknown,
    SourceUnauthorized,
    SourceUnavailable,
)
from tests.source_fixtures import OTHER, OWNER, make_attempt, reserved


def parsed_statement(attempt):
    fixture = (
        Path(__file__).resolve().parents[3] / "contracts/examples/bank-statement.json"
    )
    statement = json.loads(fixture.read_text(encoding="utf-8"), parse_float=Decimal)
    statement["source_metadata"]["document_id"] = str(attempt.document_id)
    return statement


def saved_receipt(attempt, count=3):
    return {
        "workspace_id": str(attempt.workspace_id),
        "document_id": str(attempt.document_id),
        "status": "parsed",
        "transaction_count": count,
    }


def run_save(handler, attempt, statement):
    async def run():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handler),
        ) as client:
            repository = ParsedDocumentRepository(client, OWNER, "synthetic-token")
            return await repository.finalize(reserved(attempt), statement)

    return asyncio.run(run())


def test_one_rpc_keeps_exact_numbers_unknown_fields_and_source_metadata():
    attempt = make_attempt()
    statement = parsed_statement(attempt)
    statement["transactions"][0]["credit"] = Decimal("123456789012345.6789")
    statement["transactions"][0]["balance"] = Decimal("-0.1234567890123456789")
    statement["transactions"][0]["bank_specific_note"] = "Preserved row detail"
    statement["extra_note"] = {"kept": "Preserved document detail"}
    statement["period_start"] = date(2026, 1, 1)

    def handle(request):
        assert request.method == "POST"
        assert request.url.path == "/rest/v1/rpc/finalize_bank_statement"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        assert request.headers["content-type"] == "application/json"
        body = json.loads(request.content, parse_float=Decimal)
        assert "p_user_id" not in body
        assert body["p_workspace_id"] == str(attempt.workspace_id)
        parsed = body["p_parsed_json"]
        assert parsed["transactions"][0]["credit"] == Decimal("123456789012345.6789")
        assert parsed["transactions"][0]["balance"] == Decimal("-0.1234567890123456789")
        assert b'"123456789012345.6789"' not in request.content
        assert parsed["extra_note"] == statement["extra_note"]
        assert parsed["unmapped"] == statement["unmapped"]
        assert parsed["source_locations"] == statement["source_locations"]
        assert parsed["transactions"][0]["bank_specific_note"] == "Preserved row detail"
        assert parsed["source_metadata"]["document_id"] == str(attempt.document_id)
        assert parsed["period_start"] == "2026-01-01"
        return httpx.Response(200, json=saved_receipt(attempt))

    result = run_save(handle, attempt, statement)
    assert result.status == "parsed"
    assert result.transaction_count == 3


def test_unknown_metadata_stays_null_and_zero_amounts_stay_zero():
    attempt = make_attempt()
    statement = parsed_statement(attempt)
    for field in [
        "bank",
        "account_holder",
        "account_type",
        "currency",
        "period_start",
        "period_end",
        "opening_balance",
        "closing_balance",
    ]:
        statement[field] = None

    def handle(request):
        saved = json.loads(request.content)["p_parsed_json"]
        assert saved["currency"] is None
        assert saved["closing_balance"] is None
        assert saved["transactions"][0]["debit"] == 0
        return httpx.Response(200, json=saved_receipt(attempt))

    run_save(handle, attempt, statement)


@pytest.mark.parametrize(
    "field,value",
    [
        ("debit", -1),
        ("credit", Decimal("NaN")),
        ("balance", Decimal("Infinity")),
        ("credit", 0.1),
        ("debit", True),
        ("source_row", 0),
        ("source_row", True),
        ("source_row", 1.5),
        ("date", "not-a-date"),
    ],
)
def test_bad_transaction_is_rejected_before_network_access(field, value):
    attempt = make_attempt()
    statement = parsed_statement(attempt)
    statement["transactions"][0][field] = value

    def unexpected(request):
        pytest.fail("Invalid parsed data must not reach the database.")

    with pytest.raises(ParsedDocumentRejected):
        run_save(unexpected, attempt, statement)


@pytest.mark.parametrize(
    "case",
    [
        "missing_amount",
        "wrong_document",
        "reversed_period",
        "missing_currency",
        "invalid_currency",
        "bad_extra",
        "nonfinite_extra",
    ],
)
def test_bad_statement_is_rejected_without_private_validation_details(case):
    attempt = make_attempt()
    statement = parsed_statement(attempt)
    if case == "missing_amount":
        del statement["transactions"][0]["credit"]
    elif case == "wrong_document":
        statement["source_metadata"]["document_id"] = str(OTHER)
    elif case == "reversed_period":
        statement["period_start"] = "2026-02-01"
    elif case == "missing_currency":
        del statement["currency"]
    elif case == "invalid_currency":
        statement["currency"] = "private invalid metadata"
    elif case == "bad_extra":
        statement["extra_note"] = object()
    else:
        statement["extra_note"] = Decimal("NaN")

    def unexpected(request):
        pytest.fail("Invalid parsed data must not reach the database.")

    with pytest.raises(ParsedDocumentRejected) as caught:
        run_save(unexpected, attempt, statement)
    assert "private" not in str(caught.value)


def test_foreign_owner_and_unsupported_type_stop_before_the_request():
    def unexpected(request):
        pytest.fail("An invalid caller/context must not reach the database.")

    foreign = make_attempt(user_id=OTHER)
    with pytest.raises(ValueError):
        run_save(unexpected, foreign, parsed_statement(foreign))
    balance_sheet = make_attempt(user_type="business", document_type="balance_sheet")
    with pytest.raises(UnsupportedDocumentType):
        run_save(unexpected, balance_sheet, {})


@pytest.mark.parametrize(
    "status,body,error",
    [
        (401, {}, SourceUnauthorized),
        (403, {}, SourceUnavailable),
        (404, {"code": "PT404"}, WorkspaceNotFound),
        (404, {"code": "PGRST202"}, SourceUnavailable),
        (404, [], SourceUnavailable),
        (409, {}, SourceConflict),
        (422, {}, ParsedDocumentRejected),
        (503, {}, SourceOutcomeUnknown),
        (400, {"message": "private SQL details"}, SourceUnavailable),
    ],
)
def test_errors_are_typed_and_no_write_is_automatically_retried(status, body, error):
    attempt = make_attempt()
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, json=body)

    with pytest.raises(error) as caught:
        run_save(handle, attempt, parsed_statement(attempt))
    assert len(calls) == 1
    assert "private" not in str(caught.value)


@pytest.mark.parametrize(
    "case", ["workspace", "document", "count", "status", "malformed"]
)
def test_bad_receipt_means_unknown_outcome_not_a_safe_rollback(case):
    attempt = make_attempt()
    receipt = saved_receipt(attempt)
    if case == "workspace":
        receipt["workspace_id"] = str(OTHER)
    elif case == "document":
        receipt["document_id"] = str(OTHER)
    elif case == "count":
        receipt["transaction_count"] = 999
    elif case == "status":
        receipt["status"] = "uploaded"
    else:
        receipt = []
    with pytest.raises(SourceOutcomeUnknown) as caught:
        run_save(
            lambda request: httpx.Response(200, json=receipt),
            attempt,
            parsed_statement(attempt),
        )
    assert caught.value.operation == "finalization"


def test_timeout_does_not_delete_storage_or_retry_the_save():
    attempt = make_attempt()
    calls = []

    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout("private network details", request=request)

    with pytest.raises(SourceOutcomeUnknown) as caught:
        run_save(timeout, attempt, parsed_statement(attempt))
    assert caught.value.operation == "finalization"
    assert len(calls) == 1


def test_finalization_dependency_authenticates_before_any_database_access():
    app = FastAPI()

    async def unexpected_client():
        pytest.fail("Missing credentials must stop the save.")
        yield

    app.dependency_overrides[get_auth_client] = unexpected_client

    @app.post("/save-test")
    async def save(
        repository: Annotated[
            ParsedDocumentRepository, Depends(get_parsed_document_repository)
        ],
    ):
        pytest.fail("Missing credentials must stop the route.")

    with TestClient(app) as client:
        assert client.post("/save-test").status_code == 401


def test_empty_transaction_list_is_preserved_instead_of_inventing_rows():
    attempt = make_attempt()
    statement = parsed_statement(attempt)
    statement["transactions"] = []

    def handle(request):
        assert json.loads(request.content)["p_parsed_json"]["transactions"] == []
        return httpx.Response(200, json=saved_receipt(attempt, count=0))

    assert run_save(handle, attempt, statement).transaction_count == 0


def test_authenticated_requests_keep_the_original_users_token_and_document():
    app = FastAPI()
    users = {"Bearer token-a": OWNER, "Bearer token-b": OTHER}
    attempts = {}
    calls = []

    def handle(request):
        token = request.headers["authorization"]
        calls.append(request.url.path)
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": str(users[token])})
        assert request.url.path == "/rest/v1/rpc/finalize_bank_statement"
        attempt = attempts[users[token]]
        body = json.loads(request.content)
        assert body["p_document_id"] == str(attempt.document_id)
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        return httpx.Response(200, json=saved_receipt(attempt))

    async def mock_client():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handle),
        ) as client:
            yield client

    app.dependency_overrides[get_auth_client] = mock_client

    @app.post("/save-test")
    async def save(
        user: Annotated[CurrentUser, Depends(require_user)],
        repository: Annotated[
            ParsedDocumentRepository, Depends(get_parsed_document_repository)
        ],
    ):
        attempt = make_attempt(user_id=user.id)
        attempts[user.id] = attempt
        return await repository.finalize(reserved(attempt), parsed_statement(attempt))

    with TestClient(app) as client:
        for token in ("token-a", "token-b", "token-a"):
            assert (
                client.post(
                    "/save-test", headers={"Authorization": f"Bearer {token}"}
                ).status_code
                == 200
            )
    assert calls == ["/auth/v1/user", "/rest/v1/rpc/finalize_bank_statement"] * 3
