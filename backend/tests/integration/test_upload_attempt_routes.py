"""Public upload recovery through real migrations with synthetic Auth and Storage."""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.core.security import get_auth_client
from tests.integration.test_persistence_recovery import (
    LocalSupabase,
    layout_bytes,
    local_api_connection,
    statement_upload,
)
from tests.integration.test_persistence_recovery import database as database
from tests.source_fixtures import OWNER

ATTEMPTS = "/api/upload-attempts"
OWNER_HEADERS = {"Authorization": "Bearer token-a"}
OTHER_HEADERS = {"Authorization": "Bearer token-b"}
SUMMARY_FIELDS = {
    "attempt_id",
    "workspace_id",
    "document_id",
    "document_type",
    "status",
    "last_error_code",
    "receipt",
    "created_at",
    "updated_at",
}


def client_for(server):
    app = FastAPI()
    app.include_router(api_router, prefix="/api")

    async def connection():
        async with local_api_connection(server) as client:
            yield client

    app.dependency_overrides[get_auth_client] = connection
    return TestClient(app)


def recover(client, attempt_id, headers=OWNER_HEADERS):
    return client.post(f"{ATTEMPTS}/{attempt_id}/recover", headers=headers, json={})


@pytest.mark.parametrize("kind", ["bank_statement", "balance_sheet"])
@pytest.mark.parametrize(
    "fault,code,recorded,settled",
    [
        ("create_upload_attempt", "reconciliation_required", "pending", "cleaned"),
        ("upload", "cleanup_required", "pending", "cleaned"),
        ("finalize", None, "completed", "completed"),
        ("settle_upload_attempt", "reconciliation_required", "completed", "completed"),
    ],
)
def test_find_and_recover_after_lost_upload_reply(
    database, kind, fault, code, recorded, settled
):
    server = LocalSupabase(database)
    server.timeout_after = f"finalize_{kind}" if fault == "finalize" else fault
    server.reject_delete = fault == "upload"
    content = layout_bytes("a", "csv", document_type=kind)
    user_type = "business" if kind == "balance_sheet" else "personal"

    before = server.query(
        "select count(*)::int as total from public.workspaces", user=OWNER
    )["rows"]
    with client_for(server) as original_client:
        initial = statement_upload(
            original_client, content, user_type=user_type, document_type=kind
        )
        if code is None:
            assert initial.status_code == 201, initial.text
        else:
            assert initial.status_code == 503, initial.text
            assert initial.json()["detail"]["code"] == code
    if fault == "create_upload_attempt":
        assert not server.files
        assert (
            server.query(
                "select count(*)::int as total from public.workspaces", user=OWNER
            )["rows"]
            == before
        )

    # A separate app and request dependency rebuild the service from current Auth.
    with client_for(server) as client:
        page = client.get(f"{ATTEMPTS}?limit=1&offset=0", headers=OWNER_HEADERS)
        assert page.status_code == 200, page.text
        data = page.json()
        assert (data["limit"], data["offset"]) == (1, 0)
        assert data["total"] >= 1
        (summary,) = data["items"]
        assert set(summary) == SUMMARY_FIELDS
        assert (summary["document_type"], summary["status"]) == (kind, recorded)
        attempt_id = summary["attempt_id"]
        if code:
            assert initial.json()["detail"]["attempt_id"] == attempt_id
        detail = client.get(f"{ATTEMPTS}/{attempt_id}", headers=OWNER_HEADERS)
        assert detail.status_code == 200 and detail.json() == summary

        server.reject_delete = False
        result = recover(client, attempt_id)
        assert result.status_code == 200, result.text
        assert result.json()["status"] == settled
        assert result.json()["attempt_id"] == attempt_id
        receipt = result.json()["receipt"]
        if settled == "completed":
            assert receipt == {
                "document_id": summary["document_id"],
                "workspace_id": summary["workspace_id"],
                "status": "parsed",
                "transaction_count": 0 if kind == "balance_sheet" else 3,
            }
            assert list(server.files.values()) == [content]
        else:
            assert receipt is None and not server.files
        repeated = recover(client, attempt_id)
        assert repeated.status_code == 200 and repeated.json() == result.json()
        final = client.get(f"{ATTEMPTS}/{attempt_id}", headers=OWNER_HEADERS)
        assert final.json()["status"] == settled
        assert final.json()["receipt"] == receipt


def test_cleanup_pending_lost_recovery_reply_and_new_token(database):
    server = LocalSupabase(database)
    server.reject_save = server.reject_delete = True

    with client_for(server) as client:
        initial = statement_upload(client, layout_bytes("a", "csv"))
        assert initial.status_code == 503
        attempt_id = initial.json()["detail"]["attempt_id"]
        pending = recover(client, attempt_id)
        assert pending.status_code == 503
        assert pending.json()["detail"]["code"] == "cleanup_required"
        assert pending.json()["detail"]["attempt_id"] == attempt_id
        assert server.files
        logged = client.get(f"{ATTEMPTS}/{attempt_id}", headers=OWNER_HEADERS)
        assert logged.json()["status"] == "pending"
        assert logged.json()["last_error_code"] == "cleanup_required"

        # Auth accepted the request, but Storage rejected its token during recovery.
        server.reject_delete_token = "Bearer token-a"
        server.reject_delete = False
        expired = recover(client, attempt_id)
        assert (
            expired.status_code == 401
            and expired.headers["www-authenticate"] == "Bearer"
        )
        assert expired.json()["detail"]["code"] == "auth_required"
        assert expired.json()["detail"]["attempt_id"] == attempt_id
        assert server.files
        server.tokens["Bearer fresh-token-a"] = server.tokens.pop("Bearer token-a")
        fresh = {"Authorization": "Bearer fresh-token-a"}
        assert recover(client, attempt_id).status_code == 401

        # Cleanup and journal settlement commit, then the settlement reply is lost.
        server.timeout_after = "settle_upload_attempt"
        lost = recover(client, attempt_id, fresh)
        assert lost.status_code == 503 and not server.files
        assert lost.json()["detail"]["code"] == "reconciliation_required"
        assert lost.json()["detail"]["attempt_id"] == attempt_id
        retry = recover(client, attempt_id, fresh)
        assert retry.status_code == 200 and retry.json()["status"] == "cleaned"


def test_attempts_are_owner_scoped_and_recovery_rejects_context_overrides(database):
    server = LocalSupabase(database)
    with client_for(server) as client:
        assert client.get(ATTEMPTS).status_code == 401
        invalid_upload = statement_upload(client, b"", document_type="bank_statement")
        assert invalid_upload.status_code == 422
        assert "attempt_id" not in invalid_upload.json()["detail"]
        server.timeout_after = "create_upload_attempt"
        initial = statement_upload(client, layout_bytes("a", "csv"))
        assert initial.status_code == 503
        attempt_id = initial.json()["detail"]["attempt_id"]
        missing_id = uuid4()

        foreign_page = client.get(ATTEMPTS, headers=OTHER_HEADERS)
        assert foreign_page.status_code == 200 and foreign_page.json()["items"] == []
        foreign = client.get(f"{ATTEMPTS}/{attempt_id}", headers=OTHER_HEADERS)
        missing = client.get(f"{ATTEMPTS}/{missing_id}", headers=OWNER_HEADERS)
        assert foreign.status_code == missing.status_code == 404
        assert foreign.json() == missing.json()
        foreign = recover(client, attempt_id, OTHER_HEADERS)
        missing = recover(client, missing_id)
        assert foreign.status_code == missing.status_code == 404
        assert foreign.json() == missing.json()

        invalid = client.post(
            f"{ATTEMPTS}/{attempt_id}/recover",
            headers=OWNER_HEADERS,
            json={"source_path": "private/synthetic.csv", "expected_json": {"a": 3}},
        )
        assert invalid.status_code == 422
        assert invalid.json()["detail"]["code"] == "invalid_upload_attempt_request"
        assert "private/synthetic.csv" not in invalid.text
        for query in ("limit=0", "limit=101", "offset=-1"):
            assert (
                client.get(f"{ATTEMPTS}?{query}", headers=OWNER_HEADERS).status_code
                == 422
            )

        detail = client.get(f"{ATTEMPTS}/{attempt_id}", headers=OWNER_HEADERS)
        assert detail.status_code == 200 and detail.json()["status"] == "pending"
        server.timeout_after = "list_upload_attempts"
        unavailable = client.get(ATTEMPTS, headers=OWNER_HEADERS)
        assert unavailable.status_code == 503
        assert unavailable.json()["detail"]["code"] == "reconciliation_required"


def test_conflicting_completed_attempt_requires_review_and_preserves_source(database):
    server = LocalSupabase(database)
    with client_for(server) as client:
        content = layout_bytes("a", "csv")
        uploaded = statement_upload(client, content)
        assert uploaded.status_code == 201
        document = uploaded.json()["document"]["id"]
        attempt = client.get(f"{ATTEMPTS}?limit=1", headers=OWNER_HEADERS).json()[
            "items"
        ][0]
        assert attempt["document_id"] == document
        result = server.query(
            "update public.documents set parsed_json = parsed_json || "
            '\'{"account_holder": "Synthetic changed value"}\'::jsonb where id=$1::uuid',
            [document],
        )
        assert "error" not in result
        for _ in range(2):
            response = recover(client, attempt["attempt_id"])
            assert response.status_code == 409, response.text
            assert response.json()["detail"]["code"] == "state_conflict"
            assert response.json()["detail"]["attempt_id"] == attempt["attempt_id"]
        detail = client.get(
            f"{ATTEMPTS}/{attempt['attempt_id']}", headers=OWNER_HEADERS
        )
        assert detail.status_code == 200
        assert detail.json()["status"] == "needs_review"
        assert detail.json()["receipt"] is None
        assert list(server.files.values()) == [content]
