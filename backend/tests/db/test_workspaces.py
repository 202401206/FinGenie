"""Repository boundary tests with synthetic Data API responses, no real accounts."""

import asyncio
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_auth_client
from app.db.dependencies import get_workspace_repository
from app.db.errors import (
    DatabaseUnauthorized,
    DatabaseUnavailable,
    UnsupportedDocumentType,
    WorkspaceNotFound,
)
from app.db.repositories.workspaces import WorkspaceRepository

USER_A = UUID("10000000-0000-4000-8000-000000000001")
USER_B = UUID("10000000-0000-4000-8000-000000000002")
WORKSPACE_ID = UUID("20000000-0000-4000-8000-000000000001")
DOCUMENT_ID = UUID("30000000-0000-4000-8000-000000000001")
TRANSACTION_ID = UUID("40000000-0000-4000-8000-000000000001")


def workspace(**changes):
    return {
        "id": str(WORKSPACE_ID),
        "name": "Synthetic January statement",
        "user_type": "personal",
        "document_type": "bank_statement",
        "created_at": "2026-01-31T12:00:00Z",
        **changes,
    }


def document():
    return {
        "id": str(DOCUMENT_ID),
        "status": "parsed",
        "original_filename": "synthetic-bank.csv",
        "currency": None,
        "period_start": None,
        "period_end": None,
    }


def transaction():
    return {
        "id": str(TRANSACTION_ID),
        "document_id": str(DOCUMENT_ID),
        "date": "2026-01-05",
        "description": "Synthetic purchase",
        "debit": 12,
        "credit": 0,
        "balance": -2,
        "source_row": 6,
    }


def run_repository(handler, operation, *, user_id=USER_A):
    async def run():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handler),
        ) as client:
            repository = WorkspaceRepository(client, user_id, "synthetic-token")
            return await operation(repository)

    return asyncio.run(run())


def test_workspace_page_uses_owner_token_order_and_exact_count():
    def handle(request):
        assert request.method == "GET"
        assert request.url.path == "/rest/v1/workspaces"
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        assert request.headers["prefer"] == "count=exact"
        assert dict(request.url.params) == {
            "select": "id,name,user_type,document_type,created_at",
            "user_id": f"eq.{USER_A}",
            "order": "created_at.desc,id.desc",
            "limit": "1",
            "offset": "2",
        }
        return httpx.Response(
            206, json=[workspace()], headers={"Content-Range": "2-2/7"}
        )

    page = run_repository(handle, lambda repo: repo.list_workspaces(limit=1, offset=2))
    assert (page.limit, page.offset, page.total) == (1, 2, 7)
    assert page.items[0].id == WORKSPACE_ID


@pytest.mark.parametrize("status", [200, 416])
@pytest.mark.parametrize("total", [0, 4])
def test_empty_or_past_end_page_keeps_the_real_total(status, total):
    payload = [] if status == 200 else {"code": "PGRST103"}
    page = run_repository(
        lambda request: httpx.Response(
            status, json=payload, headers={"Content-Range": f"*/{total}"}
        ),
        lambda repo: repo.list_workspaces(offset=10),
    )
    assert page.items == []
    assert (page.limit, page.offset, page.total) == (50, 10, total)


@pytest.mark.parametrize(
    "limit,offset", [(0, 0), (101, 0), (50, -1), (True, 0), (1, 1.5)]
)
def test_invalid_pagination_makes_no_database_request(limit, offset):
    def unexpected(request):
        pytest.fail("Invalid pagination must be rejected before database access.")

    with pytest.raises(ValueError):
        run_repository(
            unexpected, lambda repo: repo.list_workspaces(limit=limit, offset=offset)
        )


@pytest.mark.parametrize("user_id", [USER_A, USER_B])
def test_absent_or_unowned_workspace_does_not_query_children(user_id):
    def handle(request):
        assert request.url.path == "/rest/v1/workspaces"
        assert request.url.params["id"] == f"eq.{WORKSPACE_ID}"
        assert request.url.params["user_id"] == f"eq.{user_id}"
        return httpx.Response(200, json=[])

    with pytest.raises(WorkspaceNotFound):
        run_repository(
            handle, lambda repo: repo.list_transactions(WORKSPACE_ID), user_id=user_id
        )


def test_details_keep_nullable_metadata_and_exclude_private_fields():
    def handle(request):
        columns = request.url.params["select"].split(",")
        assert "file_path" not in columns
        assert "parsed_json" not in columns
        assert "user_id" not in columns
        if request.url.path.endswith("/workspaces"):
            return httpx.Response(200, json=[workspace()])
        assert request.url.path == "/rest/v1/documents"
        assert request.url.params["workspace_id"] == f"eq.{WORKSPACE_ID}"
        return httpx.Response(
            200, json=[{**document(), "file_path": "private", "parsed_json": {}}]
        )

    result = run_repository(handle, lambda repo: repo.get_workspace(WORKSPACE_ID))
    assert result.workspace.id == WORKSPACE_ID
    assert result.documents[0].currency is None
    assert result.documents[0].period_start is None
    assert "file_path" not in result.model_dump_json()
    assert "parsed_json" not in result.model_dump_json()


def transaction_handler(response, *, bank=True, documents=None):
    def handle(request):
        if request.url.path.endswith("/workspaces"):
            return httpx.Response(
                200,
                json=[workspace(user_type="business", document_type="balance_sheet")]
                if not bank
                else [workspace()],
            )
        if request.url.path.endswith("/documents"):
            return httpx.Response(
                200, json=[document()] if documents is None else documents
            )
        assert request.url.path == "/rest/v1/transactions"
        assert request.url.params["document_id"] == f"eq.{DOCUMENT_ID}"
        assert request.url.params["order"] == "source_row.asc,id.asc"
        assert request.headers["prefer"] == "count=exact"
        return response(request) if callable(response) else response

    return handle


def test_transactions_decode_exact_money_without_a_float_round_trip():
    # Raw JSON is deliberate: httpx's json= helper would require a Python float.
    raw = (
        '[{"id":"%s","document_id":"%s","date":"2026-01-05",'
        '"description":"Synthetic purchase","debit":123456789012345.6789,'
        '"credit":0,"balance":-0.1234567890123456789,"source_row":6}]'
        % (TRANSACTION_ID, DOCUMENT_ID)
    )
    page = run_repository(
        transaction_handler(
            httpx.Response(200, text=raw, headers={"Content-Range": "0-0/1"})
        ),
        lambda repo: repo.list_transactions(WORKSPACE_ID),
    )
    assert page.items[0].debit == Decimal("123456789012345.6789")
    assert page.items[0].balance == Decimal("-0.1234567890123456789")
    assert page.items[0].credit == Decimal(0)
    assert page.items[0].source_row == 6


def test_workspace_without_document_has_no_transactions():
    page = run_repository(
        transaction_handler(None, documents=[]),
        lambda repo: repo.list_transactions(WORKSPACE_ID),
    )
    assert page.total == 0
    assert page.items == []


def test_balance_sheet_does_not_query_bank_transactions():
    with pytest.raises(UnsupportedDocumentType):
        run_repository(
            transaction_handler(None, bank=False),
            lambda repo: repo.list_transactions(WORKSPACE_ID),
        )


@pytest.mark.parametrize(
    "row",
    [
        transaction() | {"document_id": str(WORKSPACE_ID)},
        transaction() | {"debit": -1},
        transaction() | {"balance": "NaN"},
        transaction() | {"source_row": 0},
    ],
)
def test_invalid_or_wrong_document_transactions_are_rejected(row):
    with pytest.raises(DatabaseUnavailable):
        run_repository(
            transaction_handler(
                httpx.Response(200, json=[row], headers={"Content-Range": "0-0/1"})
            ),
            lambda repo: repo.list_transactions(WORKSPACE_ID),
        )


@pytest.mark.parametrize("status", [302, 400, 403, 404, 429, 500, 503])
def test_database_failures_are_sanitized_and_not_treated_as_missing(status):
    with pytest.raises(DatabaseUnavailable) as caught:
        run_repository(
            lambda request: httpx.Response(status, text="private upstream details"),
            lambda repo: repo.get_workspace(WORKSPACE_ID),
        )
    assert "private" not in str(caught.value)


def test_expired_data_api_token_has_a_distinct_safe_failure():
    with pytest.raises(DatabaseUnauthorized):
        run_repository(
            lambda request: httpx.Response(401, text="private token details"),
            lambda repo: repo.list_workspaces(),
        )


def test_database_timeout_is_sanitized():
    def timeout(request):
        raise httpx.ReadTimeout("private connection details", request=request)

    with pytest.raises(DatabaseUnavailable) as caught:
        run_repository(timeout, lambda repo: repo.list_workspaces())
    assert "private" not in str(caught.value)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not JSON", headers={"Content-Range": "*/0"}),
        httpx.Response(
            200, json={"unexpected": "object"}, headers={"Content-Range": "*/0"}
        ),
        httpx.Response(200, json=[{}], headers={"Content-Range": "0-0/1"}),
        httpx.Response(200, json=[]),
        httpx.Response(200, json=[], headers={"Content-Range": "0-0/*"}),
        httpx.Response(200, json=[workspace()], headers={"Content-Range": "*/0"}),
        httpx.Response(
            416, json={"code": "PGRST103"}, headers={"Content-Range": "*/9"}
        ),
        httpx.Response(416, json={"code": "other"}, headers={"Content-Range": "*/0"}),
    ],
)
def test_malformed_results_or_counts_never_become_fake_success(response):
    with pytest.raises(DatabaseUnavailable):
        run_repository(lambda request: response, lambda repo: repo.list_workspaces())


def test_missing_auth_stops_before_repository_access():
    app = dependency_harness(lambda request: pytest.fail("Auth must stop the request."))
    with TestClient(app) as client:
        assert client.get("/read-test").status_code == 401


def dependency_harness(handler):
    # Exercise the real dependency without implementing Anshuman's API routes.
    app = FastAPI()

    async def mock_client():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handler),
        ) as client:
            yield client

    app.dependency_overrides[get_auth_client] = mock_client

    @app.get("/read-test")
    async def read(
        repository: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    ):
        page = await repository.list_workspaces()
        return {"items": [row.model_dump(mode="json") for row in page.items]}

    return app


def test_verified_identity_and_original_token_stay_paired_between_requests():
    calls = []
    users = {"Bearer token-a": USER_A, "Bearer token-b": USER_B}

    def handle(request):
        token = request.headers["authorization"]
        user_id = users[token]
        calls.append((request.url.path, token))
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": str(user_id)})
        assert request.url.params["user_id"] == f"eq.{user_id}"
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        return httpx.Response(
            200, json=[workspace(name=str(user_id))], headers={"Content-Range": "0-0/1"}
        )

    with TestClient(dependency_harness(handle)) as client:
        for token, user_id in [
            ("token-a", USER_A),
            ("token-b", USER_B),
            ("token-a", USER_A),
        ]:
            response = client.get(
                "/read-test", headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
            assert response.json()["items"][0]["name"] == str(user_id)
    assert [path for path, _ in calls] == [
        "/auth/v1/user",
        "/rest/v1/workspaces",
        "/auth/v1/user",
        "/rest/v1/workspaces",
        "/auth/v1/user",
        "/rest/v1/workspaces",
    ]


def test_rejected_auth_never_reaches_the_data_api():
    def handle(request):
        assert request.url.path == "/auth/v1/user"
        return httpx.Response(401, text="private auth details")

    with TestClient(dependency_harness(handle)) as client:
        response = client.get(
            "/read-test", headers={"Authorization": "Bearer rejected"}
        )
        assert response.status_code == 401
        assert "private" not in response.text
