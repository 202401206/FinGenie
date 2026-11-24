"""Settings boundaries reject malformed responses and preserve typed failures."""

import asyncio
from uuid import uuid4

import httpx
import pytest

from app.db.errors import DatabaseUnauthorized, DatabaseUnavailable
from app.db.repositories.settings import DeletionConflict, SettingsRepository
from app.db.repositories.source_uploads import SourceReservationRepository
from app.schemas.settings import PreferencesPatch
from app.services.source_errors import (
    SourceConflict,
    SourceUnauthorized,
    SourceUnavailable,
)
from tests.source_fixtures import OTHER, OWNER


def run(handler, operation):
    async def execute():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handler),
        ) as client:
            return await operation(SettingsRepository(client, OWNER, "synthetic-token"))

    return asyncio.run(execute())


@pytest.mark.parametrize(
    "rows",
    [
        {},
        [{}],
        [{"theme": "dark"}],
        [{"default_currency": "USD", "theme": "unknown"}],
        [{}, {}],
    ],
)
def test_bad_preference_rows_do_not_become_defaults(rows):
    with pytest.raises(DatabaseUnavailable):
        run(
            lambda request: httpx.Response(200, json=rows),
            lambda repo: repo.get_preferences(),
        )


@pytest.mark.parametrize(
    "payload", [{}, [], {"theme": "dark"}, {"default_currency": "USD", "theme": None}]
)
def test_bad_patch_receipts_do_not_claim_the_update_succeeded(payload):
    with pytest.raises(DatabaseUnavailable):
        run(
            lambda request: httpx.Response(200, json=payload),
            lambda repo: repo.patch_preferences(PreferencesPatch(theme="dark")),
        )


@pytest.mark.parametrize(
    "status,error",
    [
        (401, DatabaseUnauthorized),
        (403, DatabaseUnavailable),
        (404, DatabaseUnavailable),
        (409, DeletionConflict),
        (500, DatabaseUnavailable),
    ],
)
def test_http_failures_are_sanitized(status, error):
    with pytest.raises(error) as caught:
        run(
            lambda request: httpx.Response(status, text="private upstream details"),
            lambda repo: repo.get_preferences(),
        )
    assert "private" not in str(caught.value)


def test_network_and_invalid_json_failures_are_sanitized():
    def timeout(request):
        raise httpx.ReadTimeout("private network details", request=request)

    for handler in [timeout, lambda request: httpx.Response(200, text="not JSON")]:
        with pytest.raises(DatabaseUnavailable):
            run(handler, lambda repo: repo.get_preferences())


@pytest.mark.parametrize("case", ["missing_id", "wrong_id", "wrong_status"])
def test_malformed_or_mismatched_deletion_job_is_rejected(case):
    operation_id = uuid4()
    result = {"id": str(operation_id), "status": "pending"}
    if case == "missing_id":
        del result["id"]
    elif case == "wrong_id":
        result["id"] = str(uuid4())
    else:
        result["status"] = "deleted"
    with pytest.raises(DatabaseUnavailable):
        run(
            lambda request: httpx.Response(200, json=result),
            lambda repo: repo.begin_deletion(operation_id),
        )


@pytest.mark.parametrize(
    "case", ["foreign_path", "wrong_id", "oversized_batch", "wrong_shape"]
)
def test_deletion_batches_cannot_select_foreign_paths_or_unbounded_work(case):
    operation_id = uuid4()
    result = {
        "id": str(operation_id),
        "sources": [f"{OWNER}/workspace/document/source.csv"],
    }
    if case == "foreign_path":
        result["sources"] = [f"{OTHER}/workspace/document/source.csv"]
    elif case == "wrong_id":
        result["id"] = str(uuid4())
    elif case == "oversized_batch":
        result["sources"] *= 101
    else:
        result["sources"] = {}
    with pytest.raises(DatabaseUnavailable):
        run(
            lambda request: httpx.Response(200, json=result),
            lambda repo: repo.deletion_sources(operation_id),
        )


@pytest.mark.parametrize(
    "operation,payload",
    [
        ("confirm", {}),
        ("confirm", {"confirmed": False}),
        ("confirm", {"confirmed": 1}),
        ("finish", {}),
        ("finish", {"status": "pending"}),
    ],
)
def test_deletion_receipts_require_explicit_confirmation(operation, payload):
    operation_id = uuid4()
    with pytest.raises(DatabaseUnavailable):
        run(
            lambda request: httpx.Response(200, json=payload),
            lambda repo: (
                repo.confirm_sources(operation_id, [])
                if operation == "confirm"
                else repo.finish_deletion(operation_id)
            ),
        )


@pytest.mark.parametrize(
    "status,value,error",
    [
        (200, True, SourceUnavailable),
        (200, -1, SourceUnavailable),
        (200, None, SourceUnavailable),
        (401, None, SourceUnauthorized),
        (409, None, SourceConflict),
        (500, None, SourceUnavailable),
    ],
)
def test_upload_generation_is_verified_before_processing(status, value, error):
    async def execute():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(status, json={"generation": value})
            ),
        ) as client:
            with pytest.raises(error):
                await SourceReservationRepository(
                    client, OWNER, "synthetic-token"
                ).get_generation()

    asyncio.run(execute())
