"""User-scoped RPC requests, exact reconciliation input and safe receipts."""

import asyncio
import json
from decimal import Decimal
from typing import Annotated

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_auth_client, require_user
from app.db.errors import UnsupportedDocumentType
from app.db.repositories.upload_recovery import UploadRecoveryRepository
from app.schemas.responses import CurrentUser
from app.services.source_dependencies import get_upload_recovery_service
from app.services.source_errors import (
    ParsedDocumentRejected,
    SourceConflict,
    SourceOutcomeUnknown,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.upload_recovery import UploadRecoveryService
from tests.db.test_parsed_documents import parsed_statement, saved_receipt
from tests.source_fixtures import OTHER, OWNER, make_attempt


def call(handler, attempt, statement=None, *, release=False):
    async def run():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handler),
        ) as client:
            repository = UploadRecoveryRepository(client, OWNER, "synthetic-token")
            if release:
                return await repository.release(attempt)
            return await repository.begin(attempt, statement)

    return asyncio.run(run())


def test_reconciliation_uses_original_token_ids_and_exact_expected_data():
    attempt = make_attempt()
    statement = parsed_statement(attempt)
    statement["transactions"][0]["credit"] = Decimal("123456789012345.6789")
    statement["extra"] = {"preserved": True}

    def handle(request):
        assert request.url.path == "/rest/v1/rpc/begin_upload_recovery"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        data = json.loads(request.content, parse_float=Decimal)
        assert "p_user_id" not in data
        assert data["p_document_id"] == str(attempt.document_id)
        assert data["p_expected_json"]["extra"] == statement["extra"]
        assert data["p_expected_json"]["transactions"][0]["credit"] == Decimal(
            "123456789012345.6789"
        )
        assert b'"123456789012345.6789"' not in request.content
        return httpx.Response(
            200, json={"state": "completed", "receipt": saved_receipt(attempt)}
        )

    assert call(handle, attempt, statement).state == "completed"


@pytest.mark.parametrize(
    "case", ["foreign", "unsupported", "wrong_document", "float", "extra"]
)
def test_invalid_context_stops_before_network_access(case):
    attempt = make_attempt(user_id=OTHER) if case == "foreign" else make_attempt()
    if case == "unsupported":
        attempt = make_attempt(user_type="business", document_type="balance_sheet")
    statement = parsed_statement(attempt)
    if case == "wrong_document":
        statement["source_metadata"]["document_id"] = str(OTHER)
    elif case == "float":
        statement["transactions"][0]["credit"] = 0.1
    elif case == "extra":
        statement["extra"] = object()

    def unexpected(request):
        pytest.fail("Invalid recovery context must not reach Supabase.")

    error = {"foreign": ValueError, "unsupported": UnsupportedDocumentType}.get(
        case, ParsedDocumentRejected
    )
    with pytest.raises(error):
        call(unexpected, attempt, statement)


@pytest.mark.parametrize(
    "status,error",
    [
        (401, SourceUnauthorized),
        (403, SourceUnavailable),
        (404, SourceUnavailable),
        (409, SourceConflict),
        (422, ParsedDocumentRejected),
        (503, SourceOutcomeUnknown),
    ],
)
@pytest.mark.parametrize("release", [False, True])
def test_rpc_failures_are_safe_and_never_retried(status, error, release):
    attempt = make_attempt()
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, json={"message": "private database details"})

    with pytest.raises(error) as caught:
        call(handle, attempt, parsed_statement(attempt), release=release)
    assert len(calls) == 1
    assert "private" not in str(caught.value)


@pytest.mark.parametrize(
    "case", ["timeout", "bad_json", "bad_state", "wrong_document", "wrong_count"]
)
def test_lost_or_mismatched_receipt_is_an_unknown_outcome(case):
    attempt = make_attempt()
    receipt = saved_receipt(attempt)
    if case == "wrong_document":
        receipt["document_id"] = str(OTHER)
    elif case == "wrong_count":
        receipt["transaction_count"] = 99

    def handle(request):
        if case == "timeout":
            raise httpx.ReadTimeout("private timeout detail", request=request)
        if case == "bad_json":
            return httpx.Response(200, text="not-json")
        if case == "bad_state":
            return httpx.Response(200, json={"state": "failed", "receipt": receipt})
        return httpx.Response(200, json={"state": "completed", "receipt": receipt})

    with pytest.raises(SourceOutcomeUnknown) as caught:
        call(handle, attempt, parsed_statement(attempt))
    assert caught.value.operation == "recovery"


@pytest.mark.parametrize("result", [{}, {"released": False}, [], {"released": 1}])
def test_release_requires_an_explicit_database_confirmation(result):
    with pytest.raises(SourceOutcomeUnknown):
        call(
            lambda request: httpx.Response(200, json=result),
            make_attempt(),
            release=True,
        )


def test_dependency_rejects_missing_authentication_before_database_access():
    app = FastAPI()

    async def unexpected_client():
        pytest.fail("No credentials must stop before recovery access.")
        yield

    app.dependency_overrides[get_auth_client] = unexpected_client

    @app.post("/recovery-test")
    async def recover(
        service: Annotated[UploadRecoveryService, Depends(get_upload_recovery_service)],
    ):
        pytest.fail("Unauthenticated recovery must not reach the route.")

    with TestClient(app) as client:
        assert client.post("/recovery-test").status_code == 401


def test_dependency_keeps_two_users_separate_and_verifies_auth_first():
    app = FastAPI()
    users = {"Bearer token-a": OWNER, "Bearer token-b": OTHER}
    attempts = {}
    calls = []

    def handle(request):
        calls.append(request.url.path)
        owner = users[request.headers["authorization"]]
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": str(owner)})
        data = json.loads(request.content)
        attempt = attempts[owner]
        assert data["p_document_id"] == str(attempt.document_id)
        return httpx.Response(
            200, json={"state": "completed", "receipt": saved_receipt(attempt)}
        )

    async def mock_client():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            transport=httpx.MockTransport(handle),
        ) as client:
            yield client

    app.dependency_overrides[get_auth_client] = mock_client

    @app.post("/recovery-test")
    async def recover(
        user: Annotated[CurrentUser, Depends(require_user)],
        service: Annotated[UploadRecoveryService, Depends(get_upload_recovery_service)],
    ):
        attempt = make_attempt(user_id=user.id)
        attempts[user.id] = attempt
        return await service.recover(attempt, parsed_statement(attempt))

    with TestClient(app) as client:
        for token in ("token-a", "token-b", "token-a"):
            response = client.post(
                "/recovery-test", headers={"Authorization": f"Bearer {token}"}
            )
            assert (
                response.status_code == 200 and response.json()["status"] == "completed"
            )
    assert calls == ["/auth/v1/user", "/rest/v1/rpc/begin_upload_recovery"] * 3
