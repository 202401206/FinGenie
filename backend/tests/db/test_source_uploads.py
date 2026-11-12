"""Reservation and request dependency tests, independent of parsers and routes."""

import asyncio
import json
from typing import Annotated

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_auth_client
from app.db.repositories.source_uploads import SourceReservationRepository
from app.services.source_dependencies import (
    SourceUploadAccess,
    get_source_upload_access,
)
from app.services.source_errors import (
    SourceConflict,
    SourceOutcomeUnknown,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.source_models import SOURCE_BUCKET, SourceAttempt
from tests.source_fixtures import OTHER, OWNER, make_attempt, receipt


def run_reservation(handler, attempt):
    async def run():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handler),
        ) as client:
            return await SourceReservationRepository(
                client, OWNER, "synthetic-token"
            ).reserve(attempt)

    return asyncio.run(run())


def test_reservation_uses_one_user_scoped_rpc_without_an_owner_parameter():
    attempt = make_attempt()

    def handle(request):
        assert request.method == "POST"
        assert request.url.path == "/rest/v1/rpc/reserve_source_upload"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        body = json.loads(request.content)
        assert body == {
            "p_workspace_id": str(attempt.workspace_id),
            "p_document_id": str(attempt.document_id),
            "p_user_type": "personal",
            "p_document_type": "bank_statement",
            "p_name": attempt.name,
            "p_original_filename": attempt.original_filename,
            "p_file_extension": "csv",
        }
        return httpx.Response(200, json=receipt(attempt))

    result = run_reservation(handle, attempt)
    assert result.document.file_path == attempt.path
    assert result.document.status == "uploaded"


def test_reservation_rejects_another_owner_without_a_request():
    def unexpected(request):
        pytest.fail("Foreign owner must be rejected locally.")

    with pytest.raises(ValueError):
        run_reservation(unexpected, make_attempt(user_id=OTHER))


@pytest.mark.parametrize(
    "status,error",
    [
        (401, SourceUnauthorized),
        (409, SourceConflict),
        (403, SourceUnavailable),
        (404, SourceUnavailable),
        (503, SourceOutcomeUnknown),
    ],
)
def test_reservation_failure_is_safe_and_has_no_automatic_retry(status, error):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, json={"message": "private SQL details"})

    with pytest.raises(error) as caught:
        run_reservation(handle, make_attempt())
    assert len(calls) == 1
    assert "private" not in str(caught.value)


def test_lost_reservation_response_is_not_assumed_to_be_a_rollback():
    def timeout(request):
        raise httpx.ReadTimeout("private network details", request=request)

    with pytest.raises(SourceOutcomeUnknown) as caught:
        run_reservation(timeout, make_attempt())
    assert caught.value.operation == "reservation"


@pytest.mark.parametrize("change", ["workspace", "document", "path", "status", "name"])
def test_mismatched_reservation_receipt_cannot_trigger_an_upload(change):
    attempt = make_attempt()
    body = receipt(attempt)
    if change == "workspace":
        body["workspace"]["id"] = str(OTHER)
    elif change == "document":
        body["document"]["id"] = str(OTHER)
    elif change == "path":
        body["document"]["file_path"] = "wrong/path"
    elif change == "status":
        body["document"]["status"] = "parsed"
    else:
        body["workspace"]["name"] = "wrong name"
    with pytest.raises(SourceOutcomeUnknown):
        run_reservation(lambda request: httpx.Response(200, json=body), attempt)


def harness(handler):
    app = FastAPI()

    async def mock_client():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handler),
        ) as client:
            yield client

    app.dependency_overrides[get_auth_client] = mock_client

    @app.post("/source-test")
    async def upload(
        access: Annotated[SourceUploadAccess, Depends(get_source_upload_access)],
    ):
        attempt = SourceAttempt(
            user_id=access.user.id,
            user_type="personal",
            document_type="bank_statement",
            name="Synthetic statement",
            original_filename="synthetic.csv",
            kind="csv",
        )
        reservation = await access.reservations.reserve(attempt)
        await access.storage.upload(reservation, b"synthetic bytes", max_bytes=100)
        return {"reserved": True}

    return app


def test_missing_auth_stops_before_reservation_or_storage():
    def unexpected(request):
        pytest.fail("Missing authentication must stop this workflow.")

    with TestClient(harness(unexpected)) as client:
        assert client.post("/source-test").status_code == 401


def test_two_users_keep_their_tokens_and_paths_across_auth_rpc_and_storage():
    owners = {"Bearer token-a": OWNER, "Bearer token-b": OTHER}
    attempts = {}
    order = []

    def handle(request):
        token = request.headers["authorization"]
        user_id = owners[token]
        order.append(request.url.path)
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": str(user_id)})
        if request.url.path == "/rest/v1/rpc/reserve_source_upload":
            body = json.loads(request.content)
            attempt = SourceAttempt(
                user_id=user_id,
                workspace_id=body["p_workspace_id"],
                document_id=body["p_document_id"],
                user_type=body["p_user_type"],
                document_type=body["p_document_type"],
                name=body["p_name"],
                original_filename=body["p_original_filename"],
                kind=body["p_file_extension"],
            )
            attempts[token] = attempt
            return httpx.Response(200, json=receipt(attempt))
        attempt = attempts[token]
        assert request.url.path == f"/storage/v1/object/{SOURCE_BUCKET}/{attempt.path}"
        return httpx.Response(200, json={"Key": f"{SOURCE_BUCKET}/{attempt.path}"})

    with TestClient(harness(handle)) as client:
        for token in ("token-a", "token-b", "token-a"):
            response = client.post(
                "/source-test", headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
    assert len(order) == 9
    assert all(order[index] == "/auth/v1/user" for index in (0, 3, 6))
