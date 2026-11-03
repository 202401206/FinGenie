"""Workspace listing through real auth/repository wiring and synthetic HTTP."""

from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.security import get_auth_client
from app.main import app

USER_A = "10000000-0000-4000-8000-000000000001"
USER_B = "10000000-0000-4000-8000-000000000002"
WORKSPACE_A = "20000000-0000-4000-8000-000000000001"
WORKSPACE_B = "20000000-0000-4000-8000-000000000002"
HEADERS = {"Authorization": "Bearer token-a"}


def workspace(**changes):
    return {
        "id": WORKSPACE_A,
        "name": "Synthetic January statement",
        "user_type": "personal",
        "document_type": "bank_statement",
        "created_at": "2026-01-31T12:00:00Z",
        **changes,
    }


@pytest.fixture
def client() -> Iterator[TestClient]:
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides = previous


def mock_backend(database_handler, *, auth_status=200):
    """Replace only external HTTP, keeping real auth and repository dependencies."""

    def handle(request):
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        if request.url.path == "/auth/v1/user":
            if auth_status != 200:
                return httpx.Response(auth_status, text="private auth details")
            users = {"Bearer token-a": USER_A, "Bearer token-b": USER_B}
            return httpx.Response(
                200, json={"id": users[request.headers["authorization"]]}
            )
        assert request.url.path == "/rest/v1/workspaces"
        return database_handler(request)

    async def connection():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handle),
        ) as upstream:
            yield upstream

    app.dependency_overrides[get_auth_client] = connection


def test_listing_returns_only_public_fields_and_default_pagination(client):
    def database(request):
        assert request.headers["authorization"] == "Bearer token-a"
        assert request.headers["prefer"] == "count=exact"
        assert dict(request.url.params) == {
            "select": "id,name,user_type,document_type,created_at",
            "user_id": f"eq.{USER_A}",
            "order": "created_at.desc,id.desc",
            "limit": "50",
            "offset": "0",
        }
        return httpx.Response(
            200,
            json=[workspace(user_id=USER_A, file_path="private", parsed_json={})],
            headers={"Content-Range": "0-0/1"},
        )

    mock_backend(database)
    response = client.get("/api/workspaces", headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "items": [workspace()],
        "limit": 50,
        "offset": 0,
        "total": 1,
    }


@pytest.mark.parametrize("limit,offset", [(1, 0), (1, 2), (100, 0)])
def test_explicit_pagination_is_forwarded_and_total_is_preserved(client, limit, offset):
    def database(request):
        assert request.url.params["limit"] == str(limit)
        assert request.url.params["offset"] == str(offset)
        return httpx.Response(
            206,
            json=[workspace()],
            headers={"Content-Range": f"{offset}-{offset}/7"},
        )

    mock_backend(database)
    response = client.get(
        "/api/workspaces", params={"limit": limit, "offset": offset}, headers=HEADERS
    )
    assert response.status_code == 200
    assert response.json() == {
        "items": [workspace()],
        "limit": limit,
        "offset": offset,
        "total": 7,
    }


@pytest.mark.parametrize(
    "status,total,offset", [(200, 0, 0), (200, 7, 10), (416, 7, 10)]
)
def test_empty_pages_preserve_real_count(client, status, total, offset):
    mock_backend(
        lambda request: httpx.Response(
            status,
            json=[] if status == 200 else {"code": "PGRST103"},
            headers={"Content-Range": f"*/{total}"},
        )
    )
    response = client.get("/api/workspaces", params={"offset": offset}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "limit": 50,
        "offset": offset,
        "total": total,
    }


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": -1},
        {"limit": 101},
        {"limit": "abc"},
        {"limit": "1.5"},
        {"offset": -1},
        {"offset": "abc"},
        {"offset": "1.5"},
    ],
)
def test_invalid_pagination_is_422_without_database_access(client, params):
    mock_backend(lambda request: pytest.fail("Invalid input reached the database."))
    response = client.get("/api/workspaces", params=params, headers=HEADERS)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


@pytest.mark.parametrize("header", [None, "Basic abc", "Bearer", "Bearer   "])
def test_missing_or_malformed_auth_stops_before_external_access(client, header):
    async def unexpected_connection():
        pytest.fail("Missing credentials must stop before external access.")
        yield  # Keep this an async-generator dependency.

    app.dependency_overrides[get_auth_client] = unexpected_connection
    headers = {} if header is None else {"Authorization": header}
    response = client.get("/api/workspaces", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("status", [400, 401, 403])
def test_rejected_auth_stops_before_database_access(client, status):
    mock_backend(
        lambda request: pytest.fail("Rejected auth reached the database."),
        auth_status=status,
    )
    response = client.get("/api/workspaces", headers=HEADERS)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert "private" not in response.text


@pytest.mark.parametrize("status", [500, 503])
def test_auth_outage_is_safe_503(client, status):
    mock_backend(
        lambda request: pytest.fail("Auth outage reached the database."),
        auth_status=status,
    )
    response = client.get("/api/workspaces", headers=HEADERS)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "auth_unavailable"
    assert "private" not in response.text


def test_request_identity_and_original_token_stay_paired(client):
    users = {"Bearer token-a": USER_A, "Bearer token-b": USER_B}
    workspaces = {USER_A: WORKSPACE_A, USER_B: WORKSPACE_B}
    seen = []

    def database(request):
        token = request.headers["authorization"]
        user = users[token]
        assert request.url.params["user_id"] == f"eq.{user}"
        seen.append((user, token))
        return httpx.Response(
            200,
            json=[workspace(id=workspaces[user], name=user)],
            headers={"Content-Range": "0-0/1"},
        )

    mock_backend(database)
    for token, user in [("token-a", USER_A), ("token-b", USER_B), ("token-a", USER_A)]:
        response = client.get(
            "/api/workspaces", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["items"] == [workspace(id=workspaces[user], name=user)]
    assert seen == [
        (USER_A, "Bearer token-a"),
        (USER_B, "Bearer token-b"),
        (USER_A, "Bearer token-a"),
    ]


def test_repository_order_is_preserved_in_http_response(client):
    rows = [workspace(id=WORKSPACE_B), workspace(id=WORKSPACE_A)]

    def database(request):
        assert request.url.params["order"] == "created_at.desc,id.desc"
        return httpx.Response(200, json=rows, headers={"Content-Range": "0-1/2"})

    mock_backend(database)
    response = client.get("/api/workspaces", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["items"] == rows


def test_database_token_rejection_is_401(client):
    mock_backend(lambda request: httpx.Response(401, text="private database details"))
    response = client.get("/api/workspaces", headers=HEADERS)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["detail"]["code"] == "unauthorized"
    assert "private" not in response.text


@pytest.mark.parametrize("status", [302, 400, 403, 404, 429, 500, 503])
def test_database_failure_is_safe_503_not_an_empty_page(client, status):
    mock_backend(
        lambda request: httpx.Response(status, text="private database details")
    )
    response = client.get("/api/workspaces", headers=HEADERS)
    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "database_unavailable",
            "message": "Workspace data is unavailable.",
        }
    }


def test_database_timeout_is_safe_503(client):
    def timeout(request):
        raise httpx.ReadTimeout("private timeout details", request=request)

    mock_backend(timeout)
    response = client.get("/api/workspaces", headers=HEADERS)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "database_unavailable"
    assert "private" not in response.text


@pytest.mark.parametrize("payload", ["not JSON", "[{}]"])
def test_malformed_database_response_is_safe_503(client, payload):
    mock_backend(
        lambda request: httpx.Response(
            200, text=payload, headers={"Content-Range": "0-0/1"}
        )
    )
    response = client.get("/api/workspaces", headers=HEADERS)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "database_unavailable"
