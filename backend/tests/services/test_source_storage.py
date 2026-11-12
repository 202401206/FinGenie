"""Storage wire contracts, ownership, bounds and uncertain mutation outcomes."""

import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from app.services.source_errors import (
    SourceConflict,
    SourceOutcomeUnknown,
    SourceTooLarge,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.source_models import (
    SOURCE_BUCKET,
    SourceKind,
)
from app.services.source_storage import SourceStorage
from tests.source_fixtures import OTHER, OWNER, make_attempt, reserved


def run_storage(handler, operation):
    async def run():
        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handler),
        ) as client:
            return await operation(SourceStorage(client, OWNER, "synthetic-token"))

    return asyncio.run(run())


def test_attempt_generates_distinct_immutable_ids_and_a_uuid_only_path():
    first = make_attempt(original_filename="C:\\private\\synthetic.csv")
    second = make_attempt()
    assert first.workspace_id != second.workspace_id
    assert first.document_id != second.document_id
    assert first.original_filename == "synthetic.csv"
    assert first.path == f"{OWNER}/{first.workspace_id}/{first.document_id}/source.csv"
    assert "private" not in first.path
    assert "synthetic" not in first.path
    with pytest.raises(ValidationError):
        first.user_id = OTHER


def test_filename_control_characters_are_removed_from_metadata():
    attempt = make_attempt(original_filename="/private/synthetic\r\n.csv")
    assert attempt.original_filename == "synthetic__.csv"


@pytest.mark.parametrize(
    "changes",
    [
        {"original_filename": ".."},
        {"original_filename": "/private/"},
        {"name": "   "},
        {"name": "bad\nname"},
        {"kind": "pdf", "original_filename": "synthetic.pdf"},
        {"kind": "xlsx"},
        {"document_type": "balance_sheet"},
    ],
)
def test_invalid_attempt_is_rejected_before_network_access(changes):
    with pytest.raises(ValidationError):
        make_attempt(**changes)


@pytest.mark.parametrize("kind", [SourceKind.CSV, SourceKind.XLSX])
def test_upload_sends_exact_bytes_and_correct_mime_without_overwrite(kind):
    attempt = make_attempt(kind=kind, original_filename=f"synthetic.{kind.value}")
    content = b"synthetic-source-bytes"

    def handle(request):
        assert request.method == "POST"
        assert request.url.path == f"/storage/v1/object/{SOURCE_BUCKET}/{attempt.path}"
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        assert request.headers["x-upsert"] == "false"
        assert request.headers["content-type"] == kind.content_type
        assert request.content == content
        return httpx.Response(200, json={"Key": f"{SOURCE_BUCKET}/{attempt.path}"})

    run_storage(
        handle,
        lambda storage: storage.upload(reserved(attempt), content, max_bytes=100),
    )


@pytest.mark.parametrize("operation", ["upload", "remove"])
def test_other_users_context_is_rejected_before_storage_request(operation):
    attempt = make_attempt(user_id=OTHER)

    def unexpected(request):
        pytest.fail("A foreign owner must not reach Storage.")

    with pytest.raises(ValueError):
        run_storage(
            unexpected,
            lambda storage: (
                storage.upload(reserved(attempt), b"source", max_bytes=100)
                if operation == "upload"
                else storage.remove(attempt)
            ),
        )


@pytest.mark.parametrize(
    "content,limit,error",
    [
        (b"", 10, ValueError),
        ("source", 10, ValueError),
        (b"source", 0, ValueError),
        (b"source", True, ValueError),
        (b"source", 2, SourceTooLarge),
    ],
)
def test_bad_content_or_size_does_not_reach_storage(content, limit, error):
    def unexpected(request):
        pytest.fail("Invalid or oversized content must be rejected locally.")

    with pytest.raises(error):
        run_storage(
            unexpected,
            lambda storage: storage.upload(
                reserved(make_attempt()), content, max_bytes=limit
            ),
        )


def test_cleanup_uses_storage_api_and_exact_path_even_without_metadata():
    attempt = make_attempt()

    def handle(request):
        assert request.method == "DELETE"
        assert request.url.path == f"/storage/v1/object/{SOURCE_BUCKET}"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        assert json.loads(request.content) == {"prefixes": [attempt.path]}
        return httpx.Response(
            200, json=[{"name": attempt.path, "bucket_id": SOURCE_BUCKET}]
        )

    assert run_storage(handle, lambda storage: storage.remove(attempt)) is True


def test_empty_cleanup_response_is_not_a_claim_that_an_object_was_removed():
    assert (
        run_storage(
            lambda request: httpx.Response(200, json=[]),
            lambda storage: storage.remove(make_attempt()),
        )
        is False
    )


@pytest.mark.parametrize(
    "status,body,error",
    [
        (401, {}, SourceUnauthorized),
        (400, {"statusCode": "401"}, SourceUnauthorized),
        (409, {}, SourceConflict),
        (400, {"error": "Duplicate"}, SourceConflict),
        (409, {"code": "ResourceAlreadyExists"}, SourceConflict),
        (413, {}, SourceTooLarge),
        (403, {"message": "private denied details"}, SourceUnavailable),
        (400, {"message": "private rejected details"}, SourceUnavailable),
        (302, {}, SourceUnavailable),
        (503, {"message": "private server details"}, SourceOutcomeUnknown),
    ],
)
def test_storage_errors_are_typed_sanitized_and_never_retried(status, body, error):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, json=body)

    with pytest.raises(error) as caught:
        run_storage(
            handle,
            lambda storage: storage.upload(
                reserved(make_attempt()), b"source", max_bytes=100
            ),
        )
    assert len(calls) == 1
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("operation", ["upload", "removal"])
def test_lost_response_preserves_uncertainty_without_cleanup_or_retry(operation):
    calls = []

    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout("private network details", request=request)

    with pytest.raises(SourceOutcomeUnknown) as caught:
        run_storage(
            timeout,
            lambda storage: (
                storage.upload(reserved(make_attempt()), b"source", max_bytes=100)
                if operation == "upload"
                else storage.remove(make_attempt())
            ),
        )
    assert caught.value.operation == operation
    assert len(calls) == 1
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("body", [None, {}, {"Key": "wrong/path"}, []])
def test_bad_upload_receipt_is_uncertain_because_the_file_may_have_saved(body):
    with pytest.raises(SourceOutcomeUnknown):
        run_storage(
            lambda request: httpx.Response(200, json=body),
            lambda storage: storage.upload(
                reserved(make_attempt()), b"source", max_bytes=100
            ),
        )


@pytest.mark.parametrize("body", [{}, [{"name": "another/path"}], [None]])
def test_bad_cleanup_receipt_cannot_be_reported_as_success(body):
    with pytest.raises(SourceOutcomeUnknown):
        run_storage(
            lambda request: httpx.Response(200, json=body),
            lambda storage: storage.remove(make_attempt()),
        )
