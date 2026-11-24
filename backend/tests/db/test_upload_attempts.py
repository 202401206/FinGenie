"""Journal transport, safe presenters and exact context validation boundaries."""

import asyncio
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
import simplejson

from app.db.repositories.upload_attempts import UploadAttemptRepository
from app.services.source_errors import (
    ParsedDocumentRejected,
    SourceConflict,
    SourceOutcomeUnknown,
    SourceUnauthorized,
    SourceUnavailable,
)
from tests.db.test_balance_document_saves import balance_attempt, balance_statement
from tests.db.test_parsed_documents import parsed_statement
from tests.source_fixtures import OTHER, OWNER, make_attempt


def summary(attempt, identifier):
    return {
        "attempt_id": str(identifier),
        "workspace_id": str(attempt.workspace_id),
        "document_id": str(attempt.document_id),
        "document_type": attempt.document_type.value,
        "status": "pending",
        "last_error_code": None,
        "receipt": None,
        "created_at": "2026-11-20T09:00:00Z",
        "updated_at": "2026-11-20T09:00:00Z",
    }


@pytest.mark.parametrize("balance", [False, True])
def test_create_uses_verified_jwt_and_preserves_exact_extra_context(balance):
    attempt = (balance_attempt if balance else make_attempt)()
    parsed = (balance_statement if balance else parsed_statement)(attempt)
    exact = Decimal("12345678901234567890.1234567890123456789")
    parsed["prior_period"] = {"total": exact}
    identifier = uuid4()

    def handle(request):
        assert request.headers["authorization"] == "Bearer original-user-jwt"
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        payload = simplejson.loads(request.content, use_decimal=True)
        assert set(payload) == {"p_attempt_id", "p_context", "p_expected_json"}
        assert payload["p_expected_json"]["prior_period"]["total"] == exact
        assert payload["p_context"] == attempt.model_dump(mode="json")
        assert "original-user-jwt" not in request.content.decode()
        return httpx.Response(200, json=summary(attempt, identifier))

    async def run():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handle),
        ) as client:
            saved = await UploadAttemptRepository(
                client, OWNER, "original-user-jwt"
            ).create(attempt, parsed, attempt_id=identifier)
            assert saved.attempt_id == identifier

    asyncio.run(run())


@pytest.mark.parametrize("fault", ["foreign", "float", "wrong_document", "nonfinite"])
def test_invalid_private_context_is_rejected_before_http(fault):
    attempt = balance_attempt(user_id=OTHER if fault == "foreign" else OWNER)
    parsed = balance_statement(attempt)
    if fault == "float":
        parsed["extra"] = {"amount": 0.1}
    if fault == "wrong_document":
        parsed["source_metadata"]["document_id"] = str(uuid4())
    if fault == "nonfinite":
        parsed["extra"] = Decimal("NaN")

    def handle(request):
        pytest.fail("Invalid journal context reached the network")

    async def run():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            transport=httpx.MockTransport(handle),
        ) as client:
            with pytest.raises(
                ValueError if fault == "foreign" else ParsedDocumentRejected
            ):
                await UploadAttemptRepository(client, OWNER, "jwt").create(
                    attempt, parsed, attempt_id=uuid4()
                )

    asyncio.run(run())


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_id",
        "wrong_document",
        "nonzero_balance_receipt",
        "malformed_json",
        "receipt_on_pending",
        "private_extra_field",
    ],
)
def test_untrusted_journal_receipts_do_not_become_confirmed_results(fault):
    attempt = balance_attempt()
    identifier = uuid4()
    data = summary(attempt, identifier)
    if fault == "wrong_id":
        data["attempt_id"] = str(uuid4())
    if fault == "wrong_document":
        data["document_id"] = str(uuid4())
    if fault in ("nonzero_balance_receipt", "receipt_on_pending"):
        data["receipt"] = {
            "workspace_id": str(attempt.workspace_id),
            "document_id": str(attempt.document_id),
            "status": "parsed",
            "transaction_count": 1,
        }
        if fault == "nonzero_balance_receipt":
            data["status"] = "completed"
    if fault == "private_extra_field":
        data["expected_json"] = {"private": "not a public summary"}

    async def run():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            transport=httpx.MockTransport(
                lambda req: httpx.Response(
                    200,
                    text="{" if fault == "malformed_json" else simplejson.dumps(data),
                )
            ),
        ) as client:
            with pytest.raises(SourceOutcomeUnknown):
                await UploadAttemptRepository(client, OWNER, "jwt").create(
                    attempt, balance_statement(attempt), attempt_id=identifier
                )

    asyncio.run(run())


@pytest.mark.parametrize(
    "status,error",
    [
        (401, SourceUnauthorized),
        (409, SourceConflict),
        (422, ParsedDocumentRejected),
        (500, SourceOutcomeUnknown),
        (403, SourceUnavailable),
    ],
)
def test_upstream_errors_are_safe_and_keep_unknown_writes_distinct(status, error):
    async def run():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            transport=httpx.MockTransport(
                lambda req: httpx.Response(status, text="private upstream data")
            ),
        ) as client:
            attempt = make_attempt()
            with pytest.raises(error) as caught:
                await UploadAttemptRepository(client, OWNER, "jwt").create(
                    attempt, parsed_statement(attempt), attempt_id=uuid4()
                )
            assert "private upstream" not in str(caught.value)

    asyncio.run(run())


@pytest.mark.parametrize(
    "limit,offset", [(0, 0), (101, 0), (1, -1), (True, 0), (1, False), (1.5, 0)]
)
def test_listing_bounds_reject_invalid_values_without_network(limit, offset):
    def handle(request):
        pytest.fail("Invalid pagination reached the network")

    async def run():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            transport=httpx.MockTransport(handle),
        ) as client:
            with pytest.raises(ValueError):
                await UploadAttemptRepository(client, OWNER, "jwt").list_attempts(
                    limit=limit, offset=offset
                )

    asyncio.run(run())


def test_summary_queries_select_only_safe_fields_and_explicit_owner():
    attempt, identifier = make_attempt(), uuid4()

    def handle(request):
        assert request.url.params["user_id"] == f"eq.{OWNER}"
        fields = request.url.params["select"]
        assert all(
            value not in fields
            for value in [
                "expected_json",
                "original_filename",
                "upload_generation",
                "user_id",
                "name",
            ]
        )
        return httpx.Response(200, json=[summary(attempt, identifier)])

    async def run():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            transport=httpx.MockTransport(handle),
        ) as client:
            result = await UploadAttemptRepository(client, OWNER, "jwt").get_summary(
                identifier
            )
            assert result.attempt_id == identifier

    asyncio.run(run())


@pytest.mark.parametrize("empty", [False, True])
def test_listing_returns_bounded_page_with_total_and_safe_summaries(empty):
    attempt, identifier = make_attempt(), uuid4()

    def handle(request):
        assert request.url.path.endswith("/list_upload_attempts")
        assert simplejson.loads(request.content) == {"p_limit": 10, "p_offset": 2}
        return httpx.Response(
            200,
            json={
                "items": [] if empty else [summary(attempt, identifier)],
                "limit": 10,
                "offset": 2,
                "total": 1 if empty else 3,
            },
        )

    async def run():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            transport=httpx.MockTransport(handle),
        ) as client:
            page = await UploadAttemptRepository(client, OWNER, "jwt").list_attempts(
                limit=10, offset=2
            )
            assert page.limit == 10 and page.offset == 2
            assert page.total == (1 if empty else 3)
            assert len(page.items) == (0 if empty else 1)

    asyncio.run(run())
