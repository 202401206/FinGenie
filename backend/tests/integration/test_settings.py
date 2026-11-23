"""Settings HTTP contracts through real PostgreSQL/RLS and synthetic Storage."""

import asyncio
import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.security import get_auth_client
from app.db.repositories.source_uploads import SourceReservationRepository
from app.main import app
from app.services.source_errors import SourceConflict
from tests.db.test_balance_document_saves import balance_attempt, balance_statement
from tests.db.test_parsed_documents import parsed_statement
from tests.integration.test_persistence_recovery import LocalSupabase, helpers, store
from tests.integration.test_persistence_recovery import database as database
from tests.source_fixtures import OTHER, OWNER, make_attempt


class SettingsSupabase(LocalSupabase):
    def __init__(self, query):
        super().__init__(query)
        self.fault = None
        self.calls = []
        self.storage_receipt_only = False
        self.empty_receipt = False

    def handle(self, request):
        self.calls.append(request.url.path)
        user = {"Bearer token-a": OWNER, "Bearer token-b": OTHER}.get(
            request.headers.get("authorization")
        )
        if user is None:
            return httpx.Response(401)
        name = request.url.path.rsplit("/", 1)[-1]
        if name == self.fault:
            return httpx.Response(503, text="private upstream details")
        if name == "user_preferences":
            assert request.url.params["user_id"] == f"eq.{user}"
            result = self.query(
                "select default_currency,theme from public.user_preferences where user_id=$1",
                [str(user)],
                user,
            )
            return httpx.Response(200, json=result["rows"])
        functions = {
            "patch_user_preferences": "($1::jsonb->'p_patch')",
            "begin_financial_data_deletion": "($1::jsonb->>'p_operation_id')::uuid",
            "get_financial_data_deletion_sources": "($1::jsonb->>'p_operation_id')::uuid,($1::jsonb->>'p_limit')::int",
            "confirm_financial_data_sources_removed": "($1::jsonb->>'p_operation_id')::uuid,array(select jsonb_array_elements_text($1::jsonb->'p_paths'))",
            "finish_financial_data_deletion": "($1::jsonb->>'p_operation_id')::uuid",
        }
        if name in functions:
            assert request.headers["apikey"] == "sb_publishable_synthetic"
            result = self.query(
                f"select public.{name}({functions[name]})::text as body",
                [request.content.decode()],
                user,
            )
            if "error" in result:
                if result["error"] == "PT410":
                    return httpx.Response(410, json={"code": "PT410"})
                return self.error_response(result)
            if self.timeout_after == name:
                self.timeout_after = None
                raise httpx.ReadTimeout(
                    "Synthetic lost response after commit", request=request
                )
            return httpx.Response(200, text=result["rows"][0]["body"])
        if (
            request.method == "DELETE"
            and request.url.path == "/storage/v1/object/financial-documents"
        ):
            if self.reject_delete:
                return httpx.Response(503)
            paths = json.loads(request.content)["prefixes"]
            assert paths and all(p.startswith(f"{user}/") for p in paths)
            if self.storage_receipt_only:
                return httpx.Response(200, json=[])
            result = self.query(
                "delete from storage.objects where bucket_id='financial-documents' and name=any($1::text[]) returning name",
                [paths],
                user,
            )
            assert "error" not in result, result
            for row in result["rows"]:
                self.files.pop(row["name"], None)
            if self.timeout_after == "storage_delete":
                self.timeout_after = None
                raise httpx.ReadTimeout(
                    "Synthetic lost Storage response", request=request
                )
            return httpx.Response(
                200, json=[] if self.empty_receipt else result["rows"]
            )
        return super().handle(request)


@pytest.fixture
def settings_client(database):
    result = database(
        "truncate public.data_deletion_sources,public.data_deletion_jobs,public.financial_data_state,public.user_preferences,public.upload_cancellations,public.transactions,public.documents,public.workspaces,storage.objects"
    )
    assert "error" not in result
    server = SettingsSupabase(database)
    previous = app.dependency_overrides.copy()

    async def connection():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(server.handle),
        ) as client:
            yield client

    app.dependency_overrides[get_auth_client] = connection
    try:
        with TestClient(app) as client:
            yield client, server
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def auth(token="token-a", key=None):
    result = {"Authorization": f"Bearer {token}"}
    if key:
        result["Idempotency-Key"] = str(key)
    return result


def seed(server, *, token="token-a", balance=False):
    async def run():
        async with helpers(server, token) as (client, user):
            generation = await SourceReservationRepository(
                client, user.id, token
            ).get_generation()
            attempt = (balance_attempt if balance else make_attempt)(
                user_id=user.id, upload_generation=generation
            )
            statement = (balance_statement if balance else parsed_statement)(attempt)
            await store(client, user.id, token, attempt, statement)
            return attempt

    return asyncio.run(run())


def test_preferences_defaults_partial_updates_and_another_session(settings_client):
    client, server = settings_client
    assert client.get("/api/me/preferences", headers=auth()).json() == {
        "default_currency": "INR",
        "theme": "light",
    }
    assert (
        client.patch(
            "/api/me/preferences", headers=auth(), json={"theme": "dark"}
        ).status_code
        == 200
    )
    assert client.patch(
        "/api/me/preferences", headers=auth(), json={"default_currency": "USD"}
    ).json() == {"default_currency": "USD", "theme": "dark"}
    assert client.patch("/api/me/preferences", headers=auth(), json={}).json() == {
        "default_currency": "USD",
        "theme": "dark",
    }
    assert client.get("/api/me/preferences", headers=auth("token-b")).json() == {
        "default_currency": "INR",
        "theme": "light",
    }
    with TestClient(app) as fresh:
        assert fresh.get("/api/me/preferences", headers=auth()).json() == {
            "default_currency": "USD",
            "theme": "dark",
        }


@pytest.mark.parametrize(
    "currency", ["INR", "USD", "EUR", "GBP", "AED", "AUD", "CAD", "JPY"]
)
def test_each_currency_preference_is_supported_without_changing_source_data(
    settings_client, currency
):
    client, server = settings_client
    attempt = seed(server)
    assert (
        client.patch(
            "/api/me/preferences", headers=auth(), json={"default_currency": currency}
        ).status_code
        == 200
    )
    result = server.query(
        "select currency,parsed_json->>'currency' as parsed_currency from public.documents where id=$1",
        [str(attempt.document_id)],
        OWNER,
    )
    assert result["rows"] == [{"currency": "INR", "parsed_currency": "INR"}]


@pytest.mark.parametrize(
    "body",
    [
        {"theme": None},
        {"theme": "system"},
        {"theme": False},
        {"default_currency": "XXX"},
        {"user_id": str(OTHER)},
        [],
        None,
    ],
)
def test_invalid_preferences_get_a_stable_422_without_writes(settings_client, body):
    client, server = settings_client
    response = client.patch("/api/me/preferences", headers=auth(), json=body)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_preference"
    assert "patch_user_preferences" not in {p.rsplit("/", 1)[-1] for p in server.calls}


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/me/preferences"),
        ("PATCH", "/api/me/preferences"),
        ("DELETE", "/api/me/data"),
    ],
)
def test_missing_and_rejected_credentials_never_access_settings(
    settings_client, method, path
):
    client, server = settings_client
    for headers in [{}, auth("invalid")]:
        response = client.request(
            method, path, headers=headers, **({"json": {}} if method == "PATCH" else {})
        )
        assert response.status_code == 401
    assert not any("/rest/v1/" in p or "/storage/" in p for p in server.calls)


@pytest.mark.parametrize("method", ["PATCH", "DELETE"])
def test_browser_preflight_allows_settings_methods(settings_client, method):
    client, _ = settings_client
    response = client.options(
        "/api/me/preferences" if method == "PATCH" else "/api/me/data",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "authorization,content-type,idempotency-key",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_delete_bank_balance_and_orphan_sources_preserves_other_user_auth_and_preferences(
    settings_client,
):
    client, server = settings_client
    seed(server)
    seed(server, balance=True)
    foreign = seed(server, token="token-b")
    orphan = f"{OWNER}/{uuid4()}/{uuid4()}/source.csv"
    assert "error" not in server.query(
        "insert into storage.objects(bucket_id,name) values('financial-documents',$1)",
        [orphan],
    )
    server.files[orphan] = b"synthetic orphan"
    client.patch(
        "/api/me/preferences",
        headers=auth(),
        json={"theme": "dark", "default_currency": "EUR"},
    )
    key = uuid4()
    response = client.delete("/api/me/data", headers=auth(key=key))
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "deleted"}
    assert server.query("select id from public.workspaces", user=OWNER)["rows"] == []
    assert all(not path.startswith(f"{OWNER}/") for path in server.files)
    assert foreign.path in server.files
    assert client.get("/api/me/preferences", headers=auth()).json() == {
        "theme": "dark",
        "default_currency": "EUR",
    }
    assert server.query("select count(*)::int as n from auth.users")["rows"] == [
        {"n": 2}
    ]
    assert client.delete("/api/me/data", headers=auth(key=key)).status_code == 200
    assert client.delete("/api/me/data", headers=auth()).status_code == 200


@pytest.mark.parametrize(
    "failure",
    [
        "storage",
        "empty_receipt_with_object",
        "lost_storage_response",
        "finish",
        "lost_begin_response",
        "lost_finish_response",
    ],
)
def test_deletion_resumes_after_partial_failures_with_fresh_service(
    settings_client, failure
):
    client, server = settings_client
    attempt = seed(server)
    key = uuid4()
    if failure == "storage":
        server.reject_delete = True
    elif failure == "empty_receipt_with_object":
        server.storage_receipt_only = True
    elif failure == "finish":
        server.fault = "finish_financial_data_deletion"
    else:
        server.timeout_after = {
            "lost_storage_response": "storage_delete",
            "lost_begin_response": "begin_financial_data_deletion",
            "lost_finish_response": "finish_financial_data_deletion",
        }[failure]
    response = client.delete("/api/me/data", headers=auth(key=key))
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["code"] in {
        "data_deletion_pending",
        "settings_unavailable",
    }
    if failure in {"storage", "empty_receipt_with_object", "lost_begin_response"}:
        assert attempt.path in server.files
    # A separate HTTP request constructs fresh repositories; progress is in SQL.
    server.reject_delete = False
    server.storage_receipt_only = False
    server.fault = None
    response = client.delete("/api/me/data", headers=auth(key=key))
    assert response.status_code == 200, response.text
    assert attempt.path not in server.files
    assert server.query("select id from public.workspaces", user=OWNER)["rows"] == []


def test_late_upload_is_blocked_and_new_upload_after_completion_uses_new_generation(
    settings_client,
):
    client, server = settings_client
    old = make_attempt()
    key = uuid4()
    assert client.delete("/api/me/data", headers=auth(key=key)).status_code == 200

    async def reserve_old():
        async with helpers(server) as (upstream, user):
            with pytest.raises(SourceConflict):
                await SourceReservationRepository(upstream, user.id, "token-a").reserve(
                    old
                )

    asyncio.run(reserve_old())
    new = seed(server)
    assert new.upload_generation == 1
    assert client.delete("/api/me/data", headers=auth(key=key)).status_code == 409
    assert new.path in server.files
    assert client.delete("/api/me/data", headers=auth(key=uuid4())).status_code == 200


def test_empty_storage_receipt_requires_and_can_confirm_real_absence(settings_client):
    client, server = settings_client
    seed(server)
    server.empty_receipt = True
    assert client.delete("/api/me/data", headers=auth(key=uuid4())).status_code == 200


def test_preference_dependency_failures_do_not_become_defaults(settings_client):
    client, server = settings_client
    server.fault = "user_preferences"
    response = client.get("/api/me/preferences", headers=auth())
    assert response.status_code == 503
    assert "private" not in response.text


def test_pending_deletion_blocks_public_upload_before_parser_work(settings_client):
    client, server = settings_client
    seed(server)
    server.reject_delete = True
    assert client.delete("/api/me/data", headers=auth(key=uuid4())).status_code == 503
    response = client.post(
        "/api/upload",
        headers=auth(),
        data={"user_type": "personal", "document_type": "bank_statement"},
        files={"file": ("test.csv", b"not parsed", "text/csv")},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "data_deletion_in_progress"


def test_large_deletion_is_bounded_and_resumes_the_original_operation(settings_client):
    client, server = settings_client
    paths = [f"{OWNER}/{uuid4()}/{uuid4()}/source.csv" for _ in range(101)]
    result = server.query(
        "insert into storage.objects(bucket_id,name) select 'financial-documents',unnest($1::text[])",
        [paths],
    )
    assert "error" not in result
    server.files.update({path: b"synthetic" for path in paths})
    key = uuid4()
    response = client.delete("/api/me/data", headers=auth(key=key))
    assert response.status_code == 503
    assert response.json()["detail"]["operation_id"] == str(key)
    assert len(server.files) == 1
    assert client.delete("/api/me/data", headers=auth(key=key)).status_code == 200
    assert server.files == {}


def test_no_key_retry_discovers_pending_job_after_lost_begin_response(settings_client):
    client, server = settings_client
    seed(server)
    server.timeout_after = "begin_financial_data_deletion"
    assert client.delete("/api/me/data", headers=auth()).status_code == 503
    assert client.delete("/api/me/data", headers=auth()).status_code == 200


def test_failed_database_cleanup_rolls_back_rows_and_can_resume(settings_client):
    client, server = settings_client
    attempt = seed(server)
    assert "error" not in server.query("""
        create function public.test_fail_settings_delete() returns trigger language plpgsql as $$
        begin raise check_violation using message='Synthetic late database delete failure'; end; $$;
    """)
    assert "error" not in server.query(
        "create trigger test_fail_settings_delete before delete on public.documents for each row execute function public.test_fail_settings_delete()"
    )
    key = uuid4()
    try:
        assert client.delete("/api/me/data", headers=auth(key=key)).status_code == 503
        assert attempt.path not in server.files
        assert (
            len(server.query("select id from public.transactions", user=OWNER)["rows"])
            == 3
        )
    finally:
        server.query("drop trigger test_fail_settings_delete on public.documents")
        server.query("drop function public.test_fail_settings_delete()")
    assert client.delete("/api/me/data", headers=auth(key=key)).status_code == 200


def test_concurrent_partial_requests_preserve_unrelated_preferences(settings_client):
    _, _ = settings_client

    async def execute():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(
                client.patch(
                    "/api/me/preferences", headers=auth(), json={"theme": "dark"}
                ),
                client.patch(
                    "/api/me/preferences",
                    headers=auth(),
                    json={"default_currency": "JPY"},
                ),
            )
            assert all(response.status_code == 200 for response in responses)
            assert (await client.get("/api/me/preferences", headers=auth())).json() == {
                "theme": "dark",
                "default_currency": "JPY",
            }

    asyncio.run(execute())
