from collections.abc import Iterator
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.security import get_auth_client
from app.main import app

USER_A = "10000000-0000-4000-8000-000000000001"
USER_B = "10000000-0000-4000-8000-000000000002"


@pytest.fixture
def client() -> Iterator[TestClient]:
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = previous


def mock_auth(handler) -> None:
    async def auth_client():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handler),
        ) as connection:
            yield connection

    app.dependency_overrides[get_auth_client] = auth_client


@pytest.mark.parametrize("header", [None, "Basic abc", "Bearer", "Bearer   "])
def test_missing_or_malformed_token_is_401(client, header):
    headers = {} if header is None else {"Authorization": header}
    response = client.get("/api/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_unconfigured_auth_is_503_but_health_works(client):
    assert client.get("/api/health").status_code == 200
    response = client.get("/api/me", headers={"Authorization": "Bearer synthetic"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "auth_unavailable"


def test_supabase_is_consulted_and_only_verified_id_is_returned(client):
    def handle(request):
        assert request.url.path == "/auth/v1/user"
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        assert request.headers["authorization"] == "Bearer opaque-access-token"
        return httpx.Response(200, json={"id": USER_A, "email": "private@example.test"})

    mock_auth(handle)
    response = client.get(
        "/api/me", headers={"Authorization": "Bearer opaque-access-token"}
    )
    assert response.status_code == 200
    assert response.json() == {"id": USER_A}


@pytest.mark.parametrize("status", [400, 401, 403])
def test_invalid_expired_or_forbidden_tokens_are_rejected(client, status):
    mock_auth(
        lambda request: httpx.Response(status, json={"message": "private details"})
    )
    response = client.get("/api/me", headers={"Authorization": "Bearer rejected"})
    assert response.status_code == 401
    assert "private details" not in response.text


@pytest.mark.parametrize("status", [302, 429, 500, 503])
def test_dependency_failures_do_not_leak_upstream_response(client, status):
    mock_auth(lambda request: httpx.Response(status, text="private upstream details"))
    response = client.get("/api/me", headers={"Authorization": "Bearer synthetic"})
    assert response.status_code == 503
    assert "private upstream details" not in response.text


def test_auth_timeout_is_sanitized(client):
    def timeout(request):
        raise httpx.ReadTimeout("private timeout details", request=request)

    mock_auth(timeout)
    response = client.get("/api/me", headers={"Authorization": "Bearer synthetic"})
    assert response.status_code == 503
    assert "private timeout details" not in response.text


@pytest.mark.parametrize("payload", [{}, {"id": "not-a-uuid"}, [], None])
def test_malformed_upstream_user_is_not_trusted(client, payload):
    mock_auth(lambda request: httpx.Response(200, json=payload))
    response = client.get("/api/me", headers={"Authorization": "Bearer synthetic"})
    assert response.status_code == 503


def test_tokens_are_scoped_to_each_request(client):
    users = {"Bearer token-a": USER_A, "Bearer token-b": USER_B}
    mock_auth(
        lambda request: httpx.Response(
            200, json={"id": users[request.headers["authorization"]]}
        )
    )
    for token, user in [("token-a", USER_A), ("token-b", USER_B), ("token-a", USER_A)]:
        response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert UUID(response.json()["id"]) == UUID(user)
