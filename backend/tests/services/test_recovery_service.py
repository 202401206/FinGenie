"""Recovery must confirm state before deleting any file or metadata."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.db.parsed_models import ParsedSaveReceipt
from app.services.recovery_models import RecoveryDecision, RecoveryResult
from app.services.source_errors import (
    SourceConflict,
    SourceOutcomeUnknown,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.upload_recovery import UploadRecoveryService
from tests.source_fixtures import make_attempt


def run_recovery(
    decision, *, begin_error=None, remove_error=None, release_error=None, removed=True
):
    attempt = make_attempt()
    calls = []

    async def begin(context, parsed):
        assert context is attempt and parsed == {"synthetic": "statement"}
        calls.append("begin")
        if begin_error:
            raise begin_error
        return decision

    async def remove(context):
        assert context is attempt
        calls.append("remove")
        if remove_error:
            raise remove_error
        return removed

    async def release(context):
        assert context is attempt
        calls.append("release")
        if release_error:
            raise release_error

    repository = AsyncMock(begin=begin, release=release)
    storage = AsyncMock(remove=remove)
    result = asyncio.run(
        UploadRecoveryService(repository, storage).recover(
            attempt, {"synthetic": "statement"}
        )
    )
    return result, calls


def test_confirmed_save_is_returned_without_deleting_anything():
    attempt = make_attempt()
    receipt = ParsedSaveReceipt(
        workspace_id=attempt.workspace_id,
        document_id=attempt.document_id,
        status="parsed",
        transaction_count=3,
    )
    result, calls = run_recovery(RecoveryDecision(state="completed", receipt=receipt))
    assert result.status == "completed" and result.receipt == receipt
    assert calls == ["begin"]


@pytest.mark.parametrize("state", ["failed", "absent"])
@pytest.mark.parametrize("removed", [True, False])
def test_cleanup_requires_database_claim_then_storage_then_metadata(state, removed):
    result, calls = run_recovery(RecoveryDecision(state=state), removed=removed)
    assert result == RecoveryResult(status="cleaned")
    assert calls == ["begin", "remove", "release"]


def test_different_saved_state_is_preserved_for_review():
    result, calls = run_recovery(RecoveryDecision(state="conflict"))
    assert result == RecoveryResult(status="pending", reason="state_conflict")
    assert calls == ["begin"]


@pytest.mark.parametrize(
    "error,reason",
    [
        (SourceUnauthorized(), "auth_required"),
        (SourceConflict(), "reconciliation_required"),
        (SourceUnavailable(), "reconciliation_required"),
        (SourceOutcomeUnknown("recovery"), "reconciliation_required"),
    ],
)
def test_uncertain_claim_never_removes_a_source(error, reason):
    result, calls = run_recovery(None, begin_error=error)
    assert result == RecoveryResult(status="pending", reason=reason)
    assert calls == ["begin"]


@pytest.mark.parametrize("stage", ["remove", "release"])
@pytest.mark.parametrize(
    "error,reason",
    [
        (SourceUnauthorized(), "auth_required"),
        (SourceConflict(), "cleanup_required"),
        (SourceUnavailable(), "cleanup_required"),
        (SourceOutcomeUnknown("removal"), "cleanup_required"),
    ],
)
def test_cleanup_failures_remain_pending_without_automatic_retry(stage, error, reason):
    result, calls = run_recovery(
        RecoveryDecision(state="failed"), **{f"{stage}_error": error}, removed=False
    )
    assert result == RecoveryResult(status="pending", reason=reason)
    assert calls == (
        ["begin", "remove"] if stage == "remove" else ["begin", "remove", "release"]
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "completed"},
        {"status": "cleaned", "reason": "cleanup_required"},
        {"status": "pending"},
    ],
)
def test_results_cannot_claim_success_or_pending_without_the_required_evidence(payload):
    with pytest.raises(ValidationError):
        RecoveryResult.model_validate(payload)
