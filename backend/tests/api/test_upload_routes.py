"""Unmounted upload router exercised with verified auth and controlled writers."""

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.routes.upload import create_upload_router
from app.core.security import get_auth_client, require_user
from app.db.dependencies import get_parsed_document_repository, get_workspace_repository
from app.main import app as production_app
from app.services.source_dependencies import (
    get_source_upload_access,
    get_upload_recovery_service,
)
from app.services.source_errors import SourceOutcomeUnknown
from tests.upload_fixtures import UploadHarness


@pytest.fixture
def upload_client():
    harness = UploadHarness()
    app = FastAPI()
    app.include_router(create_upload_router(harness.parse), prefix="/api")

    async def auth_client():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"id": str(harness.access.user.id)}
                )
            ),
        ) as client:
            yield client

    def access(user=Depends(require_user)):
        assert user.id == harness.access.user.id
        return harness.access

    app.dependency_overrides[get_auth_client] = auth_client
    app.dependency_overrides[get_source_upload_access] = access
    app.dependency_overrides[get_parsed_document_repository] = lambda: harness.save
    app.dependency_overrides[get_upload_recovery_service] = lambda: harness.recovery
    app.dependency_overrides[get_workspace_repository] = lambda: harness.reads
    with TestClient(app) as client:
        yield client, harness


def post(
    client,
    harness,
    *,
    fields=None,
    headers=None,
    content=None,
    filename="statement.csv",
):
    return client.post(
        "/api/upload",
        data=fields
        if fields is not None
        else {"user_type": "personal", "document_type": "bank_statement"},
        files={
            "file": (
                filename,
                harness.content if content is None else content,
                "text/csv",
            )
        },
        headers={"Authorization": "Bearer synthetic"} if headers is None else headers,
    )


def test_upload_route_returns_201_only_for_confirmed_save(upload_client):
    client, harness = upload_client
    response = post(client, harness)
    assert response.status_code == 201
    assert response.json()["document"] == {
        "id": str(harness.attempt.document_id),
        "status": "parsed",
    }
    assert set(response.json()["workspace"]) == {
        "id",
        "name",
        "created_at",
        "user_type",
        "document_type",
    }
    assert harness.calls == ["parse", "reserve", "upload", "finalize"]


def test_unauthenticated_request_does_not_parse_body_or_write(upload_client):
    client, harness = upload_client
    response = post(client, harness, headers={}, content=b"x" * (6 * 1024 * 1024))
    assert response.status_code == 401
    assert harness.calls == []


@pytest.mark.parametrize(
    "fields",
    [
        {"user_type": "personal"},
        {
            "user_type": "personal",
            "document_type": "bank_statement",
            "owner_id": "foreign",
        },
        {"user_type": "current", "document_type": "bank_statement"},
        {"user_type": "business", "document_type": "balance_sheet"},
    ],
)
def test_invalid_fields_never_reach_parser(upload_client, fields):
    client, harness = upload_client
    assert post(client, harness, fields=fields).status_code == 422
    assert harness.calls == []


@pytest.mark.parametrize(
    "content,filename,status",
    ids=["empty", "pdf", "extension", "oversized"],
    argvalues=[
        (b"", "statement.csv", 422),
        (b"%PDF-private", "statement.csv", 422),
        (b"a,b", "statement.pdf", 415),
        (b"x" * (5 * 1024 * 1024 + 1), "statement.csv", 413),
    ],
)
def test_invalid_file_errors_are_safe(upload_client, content, filename, status):
    client, harness = upload_client
    response = post(client, harness, content=content, filename=filename)
    assert response.status_code == status
    assert "private" not in response.text
    assert harness.calls == []


def test_whole_multipart_body_has_a_bound(upload_client):
    client, harness = upload_client
    response = post(client, harness, content=b"x" * (6 * 1024 * 1024))
    assert response.status_code == 413
    assert harness.calls == []


def test_pending_save_does_not_return_201(upload_client):
    client, harness = upload_client
    harness.stage = "finalize"
    harness.error = SourceOutcomeUnknown("finalization")
    harness.recovery_status = "pending"
    harness.reason = "reconciliation_required"
    response = post(client, harness)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "reconciliation_required"
    assert "file_path" not in response.text


def test_production_upload_stays_unmounted_until_real_parser_is_available():
    assert "/api/upload" not in production_app.openapi()["paths"]


def test_two_uploaded_files_are_rejected(upload_client):
    client, harness = upload_client
    response = client.post(
        "/api/upload",
        data={"user_type": "personal", "document_type": "bank_statement"},
        files=[
            ("file", ("a.csv", b"a,b", "text/csv")),
            ("file", ("b.csv", b"a,b", "text/csv")),
        ],
        headers={"Authorization": "Bearer synthetic"},
    )
    assert response.status_code == 422
    assert harness.calls == []


def test_text_file_field_is_rejected(upload_client):
    client, harness = upload_client
    response = client.post(
        "/api/upload",
        data={
            "user_type": "personal",
            "document_type": "bank_statement",
            "file": "not bytes",
        },
        headers={"Authorization": "Bearer synthetic"},
    )
    assert response.status_code == 422
    assert harness.calls == []


def test_rejected_auth_cannot_reach_parser(upload_client):
    client, harness = upload_client

    async def rejected_auth():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(401, text="private")
            ),
        ) as upstream:
            yield upstream

    client.app.dependency_overrides[get_auth_client] = rejected_auth
    response = post(client, harness)
    assert response.status_code == 401
    assert "private" not in response.text
    assert harness.calls == []


def test_file_is_closed_after_parsing_failure(upload_client, monkeypatch):
    from starlette.datastructures import UploadFile

    from app.services.upload import BankParseError

    client, harness = upload_client
    harness.stage = "parse"
    harness.error = BankParseError("private")
    closed = []
    original = UploadFile.close

    async def close(file):
        await original(file)
        closed.append(file.file.closed)

    monkeypatch.setattr(UploadFile, "close", close)
    response = post(client, harness)
    assert response.status_code == 422
    assert closed and all(closed)


def test_cors_keeps_get_and_allows_post_only_for_configured_origins():
    from app.core.config import settings

    with TestClient(production_app) as client:
        for method in ["GET", "POST"]:
            response = client.options(
                "/api/upload",
                headers={
                    "Origin": settings.cors_origins[0],
                    "Access-Control-Request-Method": method,
                },
            )
            assert response.status_code == 200
        assert (
            client.options(
                "/api/upload",
                headers={
                    "Origin": "https://untrusted.example",
                    "Access-Control-Request-Method": "POST",
                },
            ).status_code
            == 400
        )
