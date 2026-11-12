"""Real repositories and PostgreSQL/RLS, with synthetic Auth and Storage HTTP.

This is a component integration test. It does not implement the team's parser,
public routes, Supabase Auth server or object-storage server.
"""

import asyncio
import json
import shutil
import subprocess
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.core.security import require_user
from app.db.errors import WorkspaceNotFound
from app.db.repositories.parsed_documents import ParsedDocumentRepository
from app.db.repositories.source_uploads import SourceReservationRepository
from app.db.repositories.upload_recovery import UploadRecoveryRepository
from app.db.repositories.workspaces import WorkspaceRepository
from app.services.source_errors import (
    SourceConflict,
    SourceOutcomeUnknown,
    SourceUnavailable,
)
from app.services.source_storage import SourceStorage
from app.services.upload_recovery import UploadRecoveryService
from tests.db.test_parsed_documents import parsed_statement
from tests.source_fixtures import OTHER, OWNER, make_attempt

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def database():
    node = shutil.which("node")
    if (
        node is None
        or not (ROOT / "supabase/tests/node_modules/@electric-sql/pglite").exists()
    ):
        pytest.skip(
            "Install Node and run npm ci --prefix supabase/tests for component integration."
        )
    process = subprocess.Popen(
        [node, str(ROOT / "supabase/tests/bridge.mjs")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    try:
        ready = process.stdout.readline()
        assert ready and json.loads(ready) == {"ready": True}, process.stderr.read()

        def query(sql, params=(), user=None):
            process.stdin.write(
                json.dumps(
                    {
                        "sql": sql,
                        "params": list(params),
                        "user_id": str(user) if user else None,
                    }
                )
                + "\n"
            )
            process.stdin.flush()
            line = process.stdout.readline()
            assert line, "The local test database stopped unexpectedly."
            return json.loads(line)

        assert "error" not in query(
            "insert into auth.users (id) values ($1), ($2)", [str(OWNER), str(OTHER)]
        )
        yield query
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        process.stdout.close()
        process.stderr.close()


class LocalSupabase:
    """Translate only the HTTP calls under test into real, user-scoped SQL."""

    def __init__(self, query):
        self.query = query
        self.files = {}
        self.timeout_after = None
        self.reject_save = False
        self.reject_delete = False

    def handle(self, request):
        user = {"Bearer token-a": OWNER, "Bearer token-b": OTHER}.get(
            request.headers.get("authorization")
        )
        if user is None:
            return httpx.Response(401)
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": str(user)})

        path = request.url.path
        if path.startswith("/rest/v1/rpc/"):
            function = path.rsplit("/", 1)[1]
            if function == "finalize_bank_statement" and self.reject_save:
                return httpx.Response(503)
            arguments = {
                "reserve_source_upload": [
                    ("workspace_id", "uuid"),
                    ("document_id", "uuid"),
                    ("user_type", "text"),
                    ("document_type", "text"),
                    ("name", "text"),
                    ("original_filename", "text"),
                    ("file_extension", "text"),
                ],
                "finalize_bank_statement": [
                    ("workspace_id", "uuid"),
                    ("document_id", "uuid"),
                    ("parsed_json", "jsonb"),
                ],
                "begin_upload_recovery": [
                    ("workspace_id", "uuid"),
                    ("document_id", "uuid"),
                    ("file_extension", "text"),
                    ("expected_json", "jsonb"),
                ],
                "release_failed_upload": [
                    ("workspace_id", "uuid"),
                    ("document_id", "uuid"),
                    ("file_extension", "text"),
                ],
            }[function]
            expressions = []
            for name, kind in arguments:
                operator = "->" if kind == "jsonb" else "->>"
                expressions.append(f"($1::jsonb{operator}'p_{name}')::{kind}")
            result = self.query(
                f"select public.{function}({','.join(expressions)})::text as body",
                [request.content.decode()],
                user,
            )
            if "error" in result:
                return self.error_response(result)
            if function == self.timeout_after:
                self.timeout_after = None
                raise httpx.ReadTimeout(
                    "Synthetic lost response after SQL commit", request=request
                )
            return httpx.Response(
                200,
                content=result["rows"][0]["body"],
                headers={"Content-Type": "application/json"},
            )

        prefix = "/storage/v1/object/financial-documents"
        if path.startswith(prefix):
            if request.method == "POST":
                name = path[len(prefix) + 1 :]
                result = self.query(
                    "insert into storage.objects (bucket_id, name) values ('financial-documents', $1)",
                    [name],
                    user,
                )
                if "error" in result:
                    return self.error_response(result)
                self.files[name] = request.content
                if self.timeout_after == "upload":
                    self.timeout_after = None
                    raise httpx.ReadTimeout(
                        "Synthetic lost Storage response", request=request
                    )
                return httpx.Response(200, json={"Key": f"financial-documents/{name}"})
            assert request.method == "DELETE"
            if self.reject_delete:
                return httpx.Response(503)
            names = json.loads(request.content)["prefixes"]
            assert len(names) == 1
            result = self.query(
                "delete from storage.objects where bucket_id = 'financial-documents' and name = $1 returning name",
                names,
                user,
            )
            if "error" in result:
                return self.error_response(result)
            for row in result["rows"]:
                self.files.pop(row["name"], None)
            return httpx.Response(200, json=result["rows"])

        table = path.removeprefix("/rest/v1/")
        assert request.method == "GET" and table in {
            "workspaces",
            "documents",
            "transactions",
        }
        params = request.url.params
        values, filters = [], []
        for column in ("id", "user_id", "workspace_id", "document_id"):
            if column in params:
                values.append(params[column].removeprefix("eq."))
                filters.append(f"{column} = ${len(values)}::uuid")
        where = " where " + " and ".join(filters) if filters else ""
        count = self.query(
            f"select count(*)::int as total from public.{table}{where}", values, user
        )["rows"][0]["total"]
        order = ""
        if "order" in params:
            assert params["order"] in {
                "created_at.desc,id.desc",
                "source_row.asc,id.asc",
            }
            order = " order by " + params["order"].replace(".", " ").replace(",", ", ")
        limit, offset = int(params.get("limit", "100")), int(params.get("offset", "0"))
        columns = params["select"]
        assert all(c.replace("_", "").isalpha() for c in columns.split(","))
        result = self.query(
            f"select coalesce(jsonb_agg(to_jsonb(r)), '[]'::jsonb)::text as body from "
            f"(select {columns} from public.{table}{where}{order} limit {limit} offset {offset}) r",
            values,
            user,
        )
        assert "error" not in result, result
        return httpx.Response(
            200,
            content=result["rows"][0]["body"],
            headers={"Content-Type": "application/json", "Content-Range": f"*/{count}"},
        )

    @staticmethod
    def error_response(result):
        code = result["error"]
        status = {
            "PT404": 404,
            "PT409": 409,
            "PT422": 422,
            "42501": 403,
            "23505": 409,
        }.get(code, 500)
        return httpx.Response(status, json={"code": code})


@asynccontextmanager
async def helpers(server, token="token-a"):
    async with httpx.AsyncClient(
        base_url="https://synthetic.supabase.co",
        headers={"apikey": "sb_publishable_synthetic"},
        transport=httpx.MockTransport(server.handle),
    ) as client:
        user = await require_user(token, client)
        yield client, user


async def store(client, owner, token, attempt, statement):
    reservation = await SourceReservationRepository(client, owner, token).reserve(
        attempt
    )
    await SourceStorage(client, owner, token).upload(
        reservation, b"synthetic,csv\n", max_bytes=100
    )
    return await ParsedDocumentRepository(client, owner, token).finalize(
        reservation, statement
    )


def recovery(client, owner=OWNER, token="token-a"):
    return UploadRecoveryService(
        UploadRecoveryRepository(client, owner, token),
        SourceStorage(client, owner, token),
    )


def test_reserve_upload_save_read_and_two_user_isolation(database):
    server = LocalSupabase(database)

    async def run():
        async with helpers(server) as (client, user):
            attempt = make_attempt(user_id=user.id)
            statement = parsed_statement(attempt)
            statement["transactions"][0]["credit"] = Decimal("123456789012345.6789")
            saved = await store(client, user.id, "token-a", attempt, statement)
            assert saved.transaction_count == 3
            reads = WorkspaceRepository(client, user.id, "token-a")
            page = await reads.list_transactions(attempt.workspace_id, limit=2)
            assert page.total == 3 and len(page.items) == 2
            assert page.items[0].credit == Decimal("123456789012345.6789")
            assert (
                await reads.list_transactions(attempt.workspace_id, offset=2)
            ).items[0].source_row == 8
            assert any(
                item.id == attempt.workspace_id
                for item in (await reads.list_workspaces()).items
            )
            async with helpers(server, "token-b") as (other, other_user):
                foreign = WorkspaceRepository(other, other_user.id, "token-b")
                assert all(
                    item.id != attempt.workspace_id
                    for item in (await foreign.list_workspaces()).items
                )
                with pytest.raises(WorkspaceNotFound):
                    await foreign.list_transactions(attempt.workspace_id)

    asyncio.run(run())


@pytest.mark.parametrize(
    "stage,expected",
    [
        ("reserve_source_upload", "cleaned"),
        ("upload", "cleaned"),
        ("finalize_bank_statement", "completed"),
    ],
)
def test_lost_committed_response_is_reconciled_before_any_cleanup(
    database, stage, expected
):
    server = LocalSupabase(database)
    server.timeout_after = stage
    attempt = make_attempt()
    statement = parsed_statement(attempt)

    async def run():
        async with helpers(server) as (client, user):
            with pytest.raises(SourceOutcomeUnknown):
                await store(client, user.id, "token-a", attempt, statement)
            result = await recovery(client).recover(attempt, statement)
            assert result.status == expected
            reads = WorkspaceRepository(client, user.id, "token-a")
            if expected == "completed":
                assert attempt.path in server.files
                assert (await reads.list_transactions(attempt.workspace_id)).total == 3
            else:
                assert attempt.path not in server.files
                with pytest.raises(WorkspaceNotFound):
                    await reads.get_workspace(attempt.workspace_id)
                with pytest.raises(SourceConflict):
                    await SourceReservationRepository(client, OWNER, "token-a").reserve(
                        attempt
                    )

    asyncio.run(run())


def test_failed_cleanup_retains_metadata_then_an_explicit_retry_finishes(database):
    server = LocalSupabase(database)
    server.reject_save = server.reject_delete = True
    attempt = make_attempt()
    statement = parsed_statement(attempt)

    async def run():
        async with helpers(server) as (client, _):
            with pytest.raises(SourceUnavailable):
                await store(client, OWNER, "token-a", attempt, statement)
            service = recovery(client)
            first = await service.recover(attempt, statement)
            assert first.status == "pending" and first.reason == "cleanup_required"
            details = await WorkspaceRepository(client, OWNER, "token-a").get_workspace(
                attempt.workspace_id
            )
            assert (
                details.documents[0].status == "failed" and attempt.path in server.files
            )
            server.reject_delete = False
            assert (await service.recover(attempt, statement)).status == "cleaned"
            assert attempt.path not in server.files
            assert (await service.recover(attempt, statement)).status == "cleaned"

    asyncio.run(run())


def test_changed_saved_data_is_preserved_for_review(database):
    server = LocalSupabase(database)
    attempt = make_attempt()
    statement = parsed_statement(attempt)

    async def run():
        async with helpers(server) as (client, _):
            await store(client, OWNER, "token-a", attempt, statement)
            altered = database(
                "update public.transactions set credit = 1 where document_id = $1",
                [str(attempt.document_id)],
                OWNER,
            )
            assert "error" not in altered
            result = await recovery(client).recover(attempt, statement)
            assert result.status == "pending" and result.reason == "state_conflict"
            assert attempt.path in server.files
            assert (
                await WorkspaceRepository(client, OWNER, "token-a").list_transactions(
                    attempt.workspace_id
                )
            ).total == 3

    asyncio.run(run())


def test_lost_cleanup_commit_can_be_rechecked_with_the_same_ids(database):
    server = LocalSupabase(database)
    server.reject_save = True
    attempt = make_attempt()
    statement = parsed_statement(attempt)

    async def run():
        async with helpers(server) as (client, _):
            with pytest.raises(SourceUnavailable):
                await store(client, OWNER, "token-a", attempt, statement)
            server.timeout_after = "release_failed_upload"
            service = recovery(client)
            first = await service.recover(attempt, statement)
            assert first.status == "pending" and first.reason == "cleanup_required"
            assert attempt.path not in server.files
            assert (await service.recover(attempt, statement)).status == "cleaned"

    asyncio.run(run())


def test_other_users_recovery_cannot_change_the_owners_saved_data(database):
    server = LocalSupabase(database)
    attempt = make_attempt()
    statement = parsed_statement(attempt)

    async def run():
        async with helpers(server) as (client, _):
            await store(client, OWNER, "token-a", attempt, statement)
            foreign_attempt = make_attempt(
                user_id=OTHER,
                workspace_id=attempt.workspace_id,
                document_id=attempt.document_id,
            )
            async with helpers(server, "token-b") as (other, _):
                result = await recovery(other, OTHER, "token-b").recover(
                    foreign_attempt, statement
                )
                # Other users see absence within their own namespace, not our rows.
                assert result.status == "cleaned"
            assert attempt.path in server.files
            page = await WorkspaceRepository(
                client, OWNER, "token-a"
            ).list_transactions(attempt.workspace_id)
            assert page.total == 3
            assert (
                await recovery(client).recover(attempt, statement)
            ).status == "completed"

    asyncio.run(run())


@pytest.fixture
def api_database_client(database):
    """Actual API/parser/repositories/RLS; synthetic Auth and Storage transport."""
    from fastapi.testclient import TestClient

    from app.core.security import get_auth_client
    from app.main import app

    server = LocalSupabase(database)
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
        app.dependency_overrides = previous


def statement_upload(client, content, kind="csv", token="token-a"):
    mime = (
        "text/csv"
        if kind == "csv"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return client.post(
        "/api/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"user_type": "personal", "document_type": "bank_statement"},
        files={"file": (f"synthetic.{kind}", content, mime)},
    )


def layout_bytes(layout, kind):
    import csv
    import io

    from openpyxl import Workbook

    name = (
        "synthetic_bank_statement.csv"
        if layout == "a"
        else "synthetic_bank_layout_b.csv"
    )
    content = (ROOT / "backend/tests/parsers/fixtures" / name).read_bytes()
    if kind == "csv":
        return content
    book = Workbook()
    book.active.title = "Synthetic account"
    for row in csv.reader(io.StringIO(content.decode("utf-8"))):
        book.active.append(row)
    output = io.BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


@pytest.mark.parametrize("layout", ["a", "b"])
@pytest.mark.parametrize("kind", ["csv", "xlsx"])
def test_public_upload_reads_and_two_user_isolation(api_database_client, layout, kind):
    client, server = api_database_client
    content = layout_bytes(layout, kind)
    uploaded = statement_upload(client, content, kind)
    assert uploaded.status_code == 201, uploaded.text
    workspace_id = uploaded.json()["workspace"]["id"]
    document_id = uploaded.json()["document"]["id"]
    headers = {"Authorization": "Bearer token-a"}
    detail_url = f"/api/workspaces/{workspace_id}"

    details = client.get(detail_url, headers=headers)
    assert details.status_code == 200
    assert details.json()["workspace"] == uploaded.json()["workspace"]
    metadata = details.json()["documents"][0]
    assert metadata["id"] == document_id
    assert metadata["status"] == "parsed"
    assert metadata["currency"] == ("INR" if layout == "a" else "USD")
    assert metadata["period_start"] == "2026-01-01"
    assert metadata["period_end"] == "2026-01-31"
    assert "file_path" not in details.text and "parsed_json" not in details.text

    transactions = client.get(
        f"{detail_url}/transactions?limit=2&offset=1", headers=headers
    )
    assert transactions.status_code == 200
    page = json.loads(transactions.content, parse_float=Decimal)
    assert (page["limit"], page["offset"], page["total"]) == (2, 1, 3)
    assert [row["source_row"] for row in page["items"]] == [7, 8]
    assert all(row["document_id"] == document_id for row in page["items"])
    assert page["items"][0]["debit"] == (
        Decimal("2000") if layout == "a" else Decimal("3500.50")
    )
    assert client.get(
        f"{detail_url}/transactions?offset=50", headers=headers
    ).json() == {
        "items": [],
        "limit": 50,
        "offset": 50,
        "total": 3,
    }

    owned = client.get("/api/workspaces", headers=headers)
    assert owned.status_code == 200
    assert workspace_id in {item["id"] for item in owned.json()["items"]}
    other_headers = {"Authorization": "Bearer token-b"}
    for url in [detail_url, f"{detail_url}/transactions"]:
        assert client.get(url, headers=other_headers).status_code == 404
    foreign_list = client.get("/api/workspaces", headers=other_headers)
    assert workspace_id not in {item["id"] for item in foreign_list.json()["items"]}
    assert content in server.files.values()


@pytest.mark.parametrize(
    "fault,status,remaining",
    [
        ("finalize_bank_statement", 201, True),
        ("reserve_source_upload", 503, False),
        ("upload", 503, False),
        ("save_failure", 503, False),
        ("cleanup_failure", 503, True),
    ],
)
def test_public_upload_real_sql_recovery(api_database_client, fault, status, remaining):
    client, server = api_database_client
    before = server.query("select id::text from public.workspaces", user=OWNER)["rows"]
    if fault in {"save_failure", "cleanup_failure"}:
        server.reject_save = True
        server.reject_delete = fault == "cleanup_failure"
    else:
        server.timeout_after = fault
    response = statement_upload(client, layout_bytes("a", "csv"))
    assert response.status_code == status, response.text
    assert bool(server.files) is remaining
    after = server.query("select id::text from public.workspaces", user=OWNER)["rows"]
    assert len(after) - len(before) == (1 if remaining else 0)
    assert "file_path" not in response.text
    if status == 201:
        workspace_id = response.json()["workspace"]["id"]
        headers = {"Authorization": "Bearer token-a"}
        page = client.get(
            f"/api/workspaces/{workspace_id}/transactions", headers=headers
        )
        assert page.status_code == 200
        assert page.json()["total"] == 3
        return
    if fault == "cleanup_failure":
        assert response.json()["detail"]["code"] == "cleanup_required"
        name = next(iter(server.files))
        document_id = name.split("/")[2]
        result = server.query(
            "select status::text from public.documents where id=$1::uuid",
            [document_id],
            OWNER,
        )
        assert result["rows"] == [{"status": "failed"}]
    else:
        assert response.json()["detail"]["code"] == "upload_unavailable"


def test_public_upload_decimal_roundtrip_through_real_postgres(api_database_client):
    client, _ = api_database_client
    content = (
        b"Date,Description,Debit,Credit,Balance\n"
        b"2026-01-01,Synthetic exact amount,123456789012345.6789,0,-0.1234567890123456789\n"
    )
    response = statement_upload(client, content)
    assert response.status_code == 201
    workspace_id = response.json()["workspace"]["id"]
    read = client.get(
        f"/api/workspaces/{workspace_id}/transactions",
        headers={"Authorization": "Bearer token-a"},
    )
    assert read.status_code == 200
    assert b"123456789012345.6789" in read.content
    row = json.loads(read.content, parse_float=Decimal)["items"][0]
    assert row["debit"] == Decimal("123456789012345.6789")
    assert row["balance"] == Decimal("-0.1234567890123456789")
    assert row["credit"] == 0


@pytest.mark.parametrize("kind", ["csv", "xlsx"])
def test_footer_words_in_narration_survive_the_complete_save_and_read(
    api_database_client, kind
):
    import csv
    import io

    from openpyxl import Workbook

    client, server = api_database_client
    rows = [
        ["Description", "Date", "Debit", "Credit", "Balance"],
        ["Total petrol purchase", "2026-01-01", "100", "0", "900"],
        ["Closing balance adjustment", "2026-01-02", "0", "50", "950"],
        ["Closing Balance: 950"],
    ]
    if kind == "csv":
        text = io.StringIO(newline="")
        csv.writer(text).writerows(rows)
        content = text.getvalue().encode()
    else:
        book = Workbook()
        for row in rows:
            book.active.append(row)
        output = io.BytesIO()
        book.save(output)
        book.close()
        content = output.getvalue()
    uploaded = statement_upload(client, content, kind)
    assert uploaded.status_code == 201, uploaded.text
    workspace_id = uploaded.json()["workspace"]["id"]
    page = client.get(
        f"/api/workspaces/{workspace_id}/transactions",
        headers={"Authorization": "Bearer token-a"},
    )
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert [item["description"] for item in page.json()["items"]] == [
        row[0] for row in rows[1:3]
    ]
    assert [item["source_row"] for item in page.json()["items"]] == [2, 3]
    assert content in server.files.values()
