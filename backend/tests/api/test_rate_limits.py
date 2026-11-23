"""Exercise limits on the mounted API with verified synthetic Auth replies."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.rate_limits import get_rate_limiter
from app.core.config import Settings, get_settings
from app.core.rate_limits import RequestRateLimiter
from app.core.security import get_auth_client
from app.db.dependencies import get_workspace_repository
from app.db.errors import WorkspaceNotFound
from app.main import app
from app.services.source_dependencies import get_source_upload_access
from tests.test_rate_limit_store import Clock

OWNER = UUID("10000000-0000-4000-8000-000000000011")
OTHER = UUID("10000000-0000-4000-8000-000000000022")
TOKENS = {"owner": OWNER, "refreshed-owner": OWNER, "other": OTHER}


@pytest.fixture
def limited_client():
    clock = Clock()
    limiter = RequestRateLimiter(clock=clock)
    config = Settings(
        _env_file=None, rate_limit_ai_requests=2, rate_limit_upload_requests=1
    )
    auth_calls = []
    repository = SimpleNamespace(
        get_parsed_document=AsyncMock(side_effect=WorkspaceNotFound),
        list_workspaces=AsyncMock(
            return_value=SimpleNamespace(items=[], limit=50, offset=0, total=0)
        ),
    )

    def auth_response(request):
        auth_calls.append(request.url.path)
        token = request.headers["authorization"].removeprefix("Bearer ")
        if token == "auth-down":
            return httpx.Response(503, text="private auth diagnostics")
        if token not in TOKENS:
            return httpx.Response(401, text="private token diagnostics")
        return httpx.Response(200, json={"id": str(TOKENS[token])})

    async def auth_client():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            transport=httpx.MockTransport(auth_response),
        ) as client:
            yield client

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_settings] = lambda: config
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    app.dependency_overrides[get_auth_client] = auth_client
    app.dependency_overrides[get_workspace_repository] = lambda: repository
    try:
        with TestClient(app) as client:
            yield SimpleNamespace(
                client=client,
                limiter=limiter,
                clock=clock,
                auth_calls=auth_calls,
                repository=repository,
            )
    finally:
        app.dependency_overrides = previous


def ai_request(state, *, token="owner", kind="summary", workspace=None, headers=None):
    return state.client.post(
        f"/api/workspaces/{workspace or uuid4()}/{kind}",
        json={"message": "Explain the statement."} if kind == "chat" else {},
        headers={"Authorization": f"Bearer {token}", **(headers or {})},
    )


def test_ai_budget_is_shared_across_routes_workspaces_and_token_refresh(limited_client):
    state = limited_client
    assert ai_request(state).status_code == 404
    assert ai_request(state, token="refreshed-owner", kind="chat").status_code == 404
    response = ai_request(state)
    assert response.status_code == 429
    assert response.json() == {
        "detail": {
            "code": "rate_limit_exceeded",
            "message": "Too many AI requests. Please retry later.",
        }
    }
    assert response.headers["retry-after"] == "60"
    assert state.auth_calls == ["/auth/v1/user"] * 3


def test_another_user_and_spoofed_headers_cannot_change_the_allowance(limited_client):
    state = limited_client
    for _ in range(2):
        assert ai_request(state).status_code == 404
    response = ai_request(
        state,
        headers={"X-User-ID": str(OTHER), "X-Forwarded-For": "203.0.113.7"},
    )
    assert response.status_code == 429
    assert ai_request(state, token="other").status_code == 404


@pytest.mark.parametrize(
    ("headers", "status"),
    [
        ({}, 401),
        ({"Authorization": "Basic owner"}, 401),
        ({"Authorization": "Bearer rejected"}, 401),
        ({"Authorization": "Bearer auth-down"}, 503),
    ],
)
def test_failed_auth_does_not_consume_a_users_allowance(
    limited_client, headers, status
):
    state = limited_client
    for _ in range(3):
        response = state.client.post(
            f"/api/workspaces/{uuid4()}/summary", json={}, headers=headers
        )
        assert response.status_code == status
        assert "private" not in response.text
    assert ai_request(state).status_code == 404
    assert ai_request(state).status_code == 404
    assert ai_request(state).status_code == 429


def test_retry_after_decreases_without_extending_the_window(limited_client):
    state = limited_client
    ai_request(state)
    ai_request(state)
    state.clock.now = 59.5
    assert ai_request(state).headers["retry-after"] == "1"
    state.clock.now = 60
    assert ai_request(state).status_code == 404


def test_upload_limit_stops_before_access_body_parsing_and_writes(limited_client):
    state = limited_client
    state.limiter.consume(OWNER, "upload", limit=1, window_seconds=60)
    access = AsyncMock(side_effect=AssertionError("Upload access must not run"))

    async def upload_access():
        return await access()

    app.dependency_overrides[get_source_upload_access] = upload_access
    response = state.client.post(
        "/api/upload",
        content=b"invalid multipart body",
        headers={
            "Authorization": "Bearer owner",
            "Content-Type": "multipart/form-data",
        },
    )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    access.assert_not_called()
    assert state.auth_calls == ["/auth/v1/user"]
    # Upload and AI allowances are independent.
    assert ai_request(state).status_code == 404


def test_upload_attempts_use_the_configured_budget_even_when_validation_fails(
    limited_client,
):
    state = limited_client
    access = AsyncMock(return_value=SimpleNamespace())

    async def upload_access():
        return await access()

    app.dependency_overrides[get_source_upload_access] = upload_access
    first = state.client.post("/api/upload", headers={"Authorization": "Bearer owner"})
    assert first.status_code == 422
    assert first.json()["detail"]["code"] == "invalid_upload_fields"
    assert access.call_count == 1
    second = state.client.post(
        "/api/upload", headers={"Authorization": "Bearer refreshed-owner"}
    )
    assert second.status_code == 429
    assert access.call_count == 1
    state.clock.now = 60
    third = state.client.post("/api/upload", headers={"Authorization": "Bearer owner"})
    assert third.status_code == 422
    assert access.call_count == 2


def test_full_counter_store_fails_closed_without_removing_another_user(limited_client):
    state = limited_client
    limiter = RequestRateLimiter(max_buckets=1, clock=state.clock)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    assert ai_request(state).status_code == 404
    response = ai_request(state, token="other")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "rate_limit_unavailable"
    assert response.headers["retry-after"] == "60"
    assert ai_request(state).status_code == 404
    assert ai_request(state).status_code == 429


def test_read_requests_and_preflight_are_not_throttled(limited_client):
    state = limited_client
    ai_request(state)
    ai_request(state)
    for _ in range(3):
        assert state.client.get("/api/health").status_code == 200
        assert (
            state.client.get(
                "/api/me", headers={"Authorization": "Bearer owner"}
            ).status_code
            == 200
        )
        assert (
            state.client.get(
                "/api/workspaces", headers={"Authorization": "Bearer owner"}
            ).status_code
            == 200
        )
        response = state.client.options(
            "/api/upload",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization,Content-Type",
            },
        )
        assert response.status_code == 200
    assert ai_request(state).status_code == 429


@pytest.mark.parametrize("kind", ["summary", "chat"])
def test_browser_can_read_retry_header(limited_client, kind):
    state = limited_client
    ai_request(state)
    ai_request(state)
    response = ai_request(state, kind=kind, headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 429
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "retry-after" in response.headers["access-control-expose-headers"].lower()


def test_openapi_advertises_rate_errors_on_expensive_routes():
    paths = app.openapi()["paths"]
    for path in (
        "/api/upload",
        "/api/workspaces/{workspace_id}/summary",
        "/api/workspaces/{workspace_id}/chat",
    ):
        response = paths[path]["post"]["responses"]["429"]
        assert response["description"]
    # An AI route can also document provider 429s, which need not have this header.
    assert "Retry-After" in paths["/api/upload"]["post"]["responses"]["429"]["headers"]


@pytest.mark.parametrize(
    "field",
    [
        "rate_limit_ai_requests",
        "rate_limit_upload_requests",
        "rate_limit_window_seconds",
        "rate_limit_max_buckets",
    ],
)
@pytest.mark.parametrize("value", [0, -1, True, 1.5, "not-a-number"])
def test_invalid_rate_settings_fail_at_startup(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_rate_settings_accept_environment_overrides(monkeypatch):
    monkeypatch.setenv("FINGENIE_RATE_LIMIT_AI_REQUESTS", "12")
    monkeypatch.setenv("FINGENIE_RATE_LIMIT_UPLOAD_REQUESTS", "4")
    monkeypatch.setenv("FINGENIE_RATE_LIMIT_WINDOW_SECONDS", "90")
    monkeypatch.setenv("FINGENIE_RATE_LIMIT_MAX_BUCKETS", "200")
    config = Settings(_env_file=None)
    assert (
        config.rate_limit_ai_requests,
        config.rate_limit_upload_requests,
        config.rate_limit_window_seconds,
        config.rate_limit_max_buckets,
    ) == (12, 4, 90, 200)
