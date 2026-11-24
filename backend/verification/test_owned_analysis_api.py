"""Explicit integration gate for A1 plus the real parser and lead persistence.

Run after integrating the real A1 route and parser, not via a test-only route.
No balance upload route, summary ownership or A4 completion is implied.
"""

import asyncio
from uuid import uuid4

import httpx
import pytest
import simplejson
from fastapi.testclient import TestClient

from app.core.security import get_auth_client
from app.main import app
from app.parsers.balance_sheet import parse_balance_sheet
from tests.db.test_balance_document_saves import balance_attempt
from tests.integration.test_persistence_recovery import database as database
from tests.integration.test_persistence_recovery import helpers, store
from tests.integration.test_settings import SettingsSupabase
from tests.integration.test_upload_journal import service
from verification.test_balance_parser_persistence import balance_bytes


@pytest.mark.parametrize("layout", ["a", "b"])
def test_complete_reported_values_and_prior_periods_do_not_hide_current_metrics(
    database, layout
):
    server = SettingsSupabase(database)
    attempt = balance_attempt()
    content = balance_bytes(layout, "csv")
    parsed = parse_balance_sheet(
        content, file_kind="csv", document_id=attempt.document_id
    ).model_dump(mode="python")

    async def setup():
        async with helpers(server) as (client, _):
            await service(client).prepare(attempt, parsed, attempt_id=uuid4())
            await store(client, attempt.user_id, "token-a", attempt, parsed)

    asyncio.run(setup())

    async def connection():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(server.handle),
        ) as client:
            yield client

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_auth_client] = connection
    try:
        with TestClient(app) as client:
            url = f"/api/workspaces/{attempt.workspace_id}/analysis"
            response = client.get(url, headers={"Authorization": "Bearer token-a"})
            assert response.status_code == 200, response.text
            body = simplejson.loads(response.content, use_decimal=True)
            assert body["workspace_id"] == str(attempt.workspace_id)
            assert body["reliability"] == "valid", body
            metric = next(m for m in body["metrics"] if m["key"] == "working_capital")
            assert metric["status"] == "available"
            assert metric["value"] == (7000000 if layout == "a" else 400000000)
            assert (
                client.get(url, headers={"Authorization": "Bearer token-b"}).status_code
                == 404
            )
            assert (
                client.get(
                    f"/api/workspaces/{uuid4()}/analysis",
                    headers={"Authorization": "Bearer token-a"},
                ).status_code
                == 404
            )
    finally:
        app.dependency_overrides = previous
