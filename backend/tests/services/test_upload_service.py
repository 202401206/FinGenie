"""Call order, exact input/output and failure recovery without production mocks."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.source_errors import (
    ParsedDocumentRejected,
    SourceConflict,
    SourceOutcomeUnknown,
    SourceTooLarge,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.upload import BankParseError, UploadProcessingError, UploadService
from app.services.upload_validation import DEFAULT_POLICY, UploadValidationError
from tests.upload_fixtures import UploadHarness


def service(harness, **kwargs):
    return UploadService(
        harness.parse,
        harness.access,
        harness.save,
        harness.recovery,
        harness.reads,
        **kwargs,
    )


def process(harness, **kwargs):
    file = harness.file()
    try:
        return asyncio.run(
            service(harness, **kwargs).process(
                file, user_type="personal", document_type="bank_statement"
            )
        )
    finally:
        asyncio.run(file.close())


def test_real_order_preserves_ids_bytes_and_exact_parsed_values():
    harness = UploadHarness()
    response = process(harness)
    assert harness.calls == ["parse", "reserve", "upload", "finalize"]
    assert response.workspace.id == harness.attempt.workspace_id
    assert response.workspace.name.startswith("Bank statement ")
    assert response.document.id == harness.attempt.document_id
    assert response.document.status == "parsed"
    assert set(response.model_dump()) == {"workspace", "document"}
    assert "file_path" not in response.model_dump_json()
    assert "transactions" not in response.model_dump_json()


def test_validation_failure_precedes_parser_and_all_writes():
    harness = UploadHarness()
    harness.content = b"%PDF-private"
    with pytest.raises(UploadValidationError):
        process(harness)
    assert harness.calls == []


def test_parser_rejection_is_safe_and_needs_no_cleanup():
    harness = UploadHarness(stage="parse", error=BankParseError("private statement"))
    with pytest.raises(UploadProcessingError) as caught:
        process(harness)
    assert caught.value.status_code == 422
    assert "private" not in str(caught.value)
    assert harness.calls == ["parse"]


@pytest.mark.parametrize("change", ["wrong_source", "float", "bad_extra", "too_many"])
def test_invalid_parser_output_is_rejected_before_reservation(change):
    harness = UploadHarness()
    original = harness.parse

    def parser(*args, **kwargs):
        model = original(*args, **kwargs)
        if change == "wrong_source":
            model.source_metadata.document_id = uuid4()
        elif change == "float":
            model.opening_balance = 1.1
        elif change == "bad_extra":
            model.model_extra["unknown"] = object()
        else:
            model.transactions = model.transactions * 4000
        return model

    harness.parse = parser
    with pytest.raises(UploadProcessingError) as caught:
        process(harness)
    assert caught.value.status_code == 422
    assert harness.calls == ["parse"]


@pytest.mark.parametrize("stage", ["reserve", "upload", "finalize"])
@pytest.mark.parametrize(
    "error,status",
    [
        (SourceUnauthorized(), 401),
        (SourceConflict(), 409),
        (SourceTooLarge(), 413),
        (SourceUnavailable(), 503),
        (ParsedDocumentRejected(), 422),
    ],
)
def test_confirmed_failures_recover_and_keep_original_failure(stage, error, status):
    harness = UploadHarness(stage=stage, error=error)
    with pytest.raises(UploadProcessingError) as caught:
        process(harness)
    expected = ["parse", "reserve", "upload", "finalize"]
    assert harness.calls == expected[: expected.index(stage) + 1] + ["recover"]
    assert caught.value.status_code == status
    assert caught.value.attempt is harness.attempt


@pytest.mark.parametrize("stage", ["reserve", "upload", "finalize"])
def test_unknown_write_outcomes_can_succeed_only_after_confirmed_recovery(stage):
    harness = UploadHarness(
        stage=stage,
        error=SourceOutcomeUnknown("finalization"),
        recovery_status="completed",
    )
    response = process(harness)
    assert response.document.status == "parsed"
    assert harness.calls.count("recover") == 1
    assert harness.calls.count(stage) == 1
    assert ("read" in harness.calls) == (stage == "reserve")


@pytest.mark.parametrize(
    "reason,status",
    [
        ("auth_required", 401),
        ("reconciliation_required", 503),
        ("cleanup_required", 503),
        ("state_conflict", 503),
    ],
)
def test_pending_recovery_never_reports_success(reason, status):
    harness = UploadHarness(
        stage="finalize",
        error=SourceOutcomeUnknown("finalization"),
        recovery_status="pending",
        reason=reason,
    )
    with pytest.raises(UploadProcessingError) as caught:
        process(harness)
    assert caught.value.status_code == status
    assert harness.calls == ["parse", "reserve", "upload", "finalize", "recover"]


def test_recovery_outage_is_a_safe_failure():
    harness = UploadHarness(
        stage="upload", error=SourceUnavailable("private"), recovery_status="raises"
    )
    with pytest.raises(UploadProcessingError) as caught:
        process(harness)
    assert caught.value.code == "reconciliation_required"
    assert "private" not in str(caught.value)


def test_recovered_workspace_metadata_must_match_attempt():
    harness = UploadHarness(
        stage="reserve",
        error=SourceOutcomeUnknown("reservation"),
        recovery_status="completed",
    )

    async def wrong(workspace_id):
        record = (await UploadHarness.get_workspace(harness, workspace_id)).workspace
        return SimpleNamespace(workspace=record.model_copy(update={"id": uuid4()}))

    harness.reads.get_workspace = wrong
    with pytest.raises(UploadProcessingError) as caught:
        process(harness)
    assert caught.value.code == "reconciliation_required"


def test_custom_policy_bounds_input_before_parsing():
    harness = UploadHarness()
    with pytest.raises(UploadValidationError):
        process(harness, policy=replace(DEFAULT_POLICY, max_bytes=2))
    assert harness.calls == []


def test_bad_finalization_receipt_is_reconciled():
    harness = UploadHarness()

    async def bad(reservation, parsed):
        await UploadHarness.finalize(harness, reservation, parsed)
        return {"not": "a receipt"}

    harness.save.finalize = bad
    with pytest.raises(UploadProcessingError) as caught:
        process(harness)
    assert caught.value.status_code == 503
    assert harness.calls[-1] == "recover"


def test_mismatched_recovery_receipt_never_reports_success():
    harness = UploadHarness(
        stage="finalize",
        error=SourceOutcomeUnknown("finalization"),
        recovery_status="completed",
    )

    async def wrong(attempt, parsed):
        result = await UploadHarness.recover(harness, attempt, parsed)
        result.receipt.workspace_id = uuid4()
        return result

    harness.recovery.recover = wrong
    with pytest.raises(UploadProcessingError) as caught:
        process(harness)
    assert caught.value.code == "reconciliation_required"


def test_recovered_save_with_unavailable_metadata_is_safe():
    from app.db.errors import DatabaseUnavailable

    harness = UploadHarness(
        stage="reserve",
        error=SourceOutcomeUnknown("reservation"),
        recovery_status="completed",
    )

    async def unavailable(workspace_id):
        raise DatabaseUnavailable("private")

    harness.reads.get_workspace = unavailable
    with pytest.raises(UploadProcessingError) as caught:
        process(harness)
    assert caught.value.status_code == 503
    assert "private" not in str(caught.value)
