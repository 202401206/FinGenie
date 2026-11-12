"""Workspace reads through real auth/repository wiring and synthetic HTTP."""

import json
from collections.abc import Iterator
from decimal import Decimal

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


def mock_backend(database_handler, *, auth_status=200, workspace_only=True):
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
        if workspace_only:
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


DOCUMENT_ID = "30000000-0000-4000-8000-000000000001"
DETAIL_URL = f"/api/workspaces/{WORKSPACE_A}"
TRANSACTIONS_URL = f"{DETAIL_URL}/transactions"


def document(**changes):
    return {
        "id": DOCUMENT_ID,
        "status": "parsed",
        "original_filename": "statement.csv",
        "currency": None,
        "period_start": None,
        "period_end": None,
        **changes,
    }


def test_details_preserve_nulls_and_hide_private_data(client):
    def database(request):
        if request.url.path == "/rest/v1/workspaces":
            assert request.url.params["id"] == f"eq.{WORKSPACE_A}"
            assert request.url.params["user_id"] == f"eq.{USER_A}"
            return httpx.Response(200, json=[workspace()])
        assert request.url.path == "/rest/v1/documents"
        assert request.url.params["workspace_id"] == f"eq.{WORKSPACE_A}"
        return httpx.Response(
            200,
            json=[
                document(
                    original_filename="C:\\private\\statement.csv",
                    file_path="private/source.csv",
                    parsed_json={"private": True},
                )
            ],
        )

    mock_backend(database, workspace_only=False)
    response = client.get(DETAIL_URL, headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"workspace": workspace(), "documents": [document()]}


@pytest.mark.parametrize("suffix", ["", "/transactions"])
def test_malformed_workspace_id_is_422(client, suffix):
    mock_backend(lambda request: pytest.fail("Invalid ID reached the database."))
    response = client.get(f"/api/workspaces/invalid{suffix}", headers=HEADERS)
    assert response.status_code == 422


@pytest.mark.parametrize("suffix", ["", "/transactions"])
def test_foreign_and_absent_workspaces_have_identical_404(client, suffix):
    def database(request):
        assert request.url.params["user_id"] == f"eq.{USER_B}"
        assert request.headers["authorization"] == "Bearer token-b"
        assert request.url.params["id"] in {f"eq.{WORKSPACE_A}", f"eq.{WORKSPACE_B}"}
        return httpx.Response(200, json=[])

    mock_backend(database)
    headers = {"Authorization": "Bearer token-b"}
    foreign = client.get(f"{DETAIL_URL}{suffix}", headers=headers)
    absent = client.get(f"/api/workspaces/{WORKSPACE_B}{suffix}", headers=headers)
    assert foreign.status_code == absent.status_code == 404
    assert (
        foreign.json()
        == absent.json()
        == {
            "detail": {"code": "workspace_not_found", "message": "Workspace not found."}
        }
    )


def test_balance_sheet_details_work_but_transactions_are_409(client):
    row = workspace(user_type="business", document_type="balance_sheet")

    def database(request):
        if request.url.path == "/rest/v1/workspaces":
            return httpx.Response(200, json=[row])
        assert request.url.path == "/rest/v1/documents"
        return httpx.Response(200, json=[document(original_filename="balance.xlsx")])

    mock_backend(database, workspace_only=False)
    assert client.get(DETAIL_URL, headers=HEADERS).json()["workspace"] == row
    response = client.get(TRANSACTIONS_URL, headers=HEADERS)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "unsupported_document_type"


def test_workspace_without_documents_has_empty_transaction_page(client):
    def database(request):
        if request.url.path == "/rest/v1/workspaces":
            return httpx.Response(200, json=[workspace()])
        assert request.url.path == "/rest/v1/documents"
        return httpx.Response(200, json=[])

    mock_backend(database, workspace_only=False)
    response = client.get(TRANSACTIONS_URL, headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"items": [], "limit": 50, "offset": 0, "total": 0}


def test_transactions_keep_numeric_decimal_precision_and_order(client):
    first = "40000000-0000-4000-8000-000000000001"
    second = "40000000-0000-4000-8000-000000000002"
    raw = (
        f'[{{"id":"{first}","document_id":"{DOCUMENT_ID}","date":"2026-01-05",'
        '"description":"Synthetic debit","debit":123456789012345.6789,'
        '"credit":0,"balance":-0.1234567890123456789,"source_row":6},'
        f'{{"id":"{second}","document_id":"{DOCUMENT_ID}","date":"2026-01-06",'
        '"description":"Synthetic credit","debit":0,"credit":1.25,'
        '"balance":0,"source_row":7}]'
    )

    def database(request):
        if request.url.path == "/rest/v1/workspaces":
            assert request.url.params["user_id"] == f"eq.{USER_A}"
            return httpx.Response(200, json=[workspace()])
        if request.url.path == "/rest/v1/documents":
            return httpx.Response(200, json=[document()])
        assert request.url.path == "/rest/v1/transactions"
        assert request.headers["authorization"] == "Bearer token-a"
        assert request.url.params["document_id"] == f"eq.{DOCUMENT_ID}"
        assert request.url.params["order"] == "source_row.asc,id.asc"
        assert request.url.params["limit"] == "2"
        assert request.url.params["offset"] == "1"
        return httpx.Response(206, text=raw, headers={"Content-Range": "1-2/4"})

    mock_backend(database, workspace_only=False)
    response = client.get(f"{TRANSACTIONS_URL}?limit=2&offset=1", headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert b"123456789012345.6789" in response.content
    payload = json.loads(response.content, parse_float=Decimal, parse_int=Decimal)
    assert (payload["limit"], payload["offset"], payload["total"]) == (2, 1, 4)
    assert payload["items"] == json.loads(raw, parse_float=Decimal, parse_int=Decimal)


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_transactions_reject_invalid_pagination(client, params):
    mock_backend(
        lambda request: pytest.fail("Invalid pagination reached the database.")
    )
    response = client.get(TRANSACTIONS_URL, params=params, headers=HEADERS)
    assert response.status_code == 422


@pytest.mark.parametrize("url", [DETAIL_URL, TRANSACTIONS_URL])
@pytest.mark.parametrize(
    "upstream,expected,code",
    [(401, 401, "unauthorized"), (500, 503, "database_unavailable")],
)
def test_detail_and_transaction_database_failures_are_safe(
    client, url, upstream, expected, code
):
    mock_backend(lambda request: httpx.Response(upstream, text="private upstream body"))
    response = client.get(url, headers=HEADERS)
    assert response.status_code == expected
    assert response.json()["detail"]["code"] == code
    assert "private" not in response.text
    if expected == 401:
        assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("url", [DETAIL_URL, TRANSACTIONS_URL])
def test_detail_and_transaction_routes_require_auth(client, url):
    mock_backend(
        lambda request: pytest.fail("Unauthenticated request reached the database.")
    )
    response = client.get(url)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
