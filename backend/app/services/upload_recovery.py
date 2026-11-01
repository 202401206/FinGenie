"""Recover an attempt after the calling workflow has stopped with a failure."""

from app.db.repositories.upload_recovery import UploadRecoveryRepository
from app.services.recovery_models import RecoveryResult
from app.services.source_errors import (
    SourceConflict,
    SourceTooLarge,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.source_models import SourceAttempt
from app.services.source_storage import SourceStorage


class UploadRecoveryService:
    def __init__(
        self, repository: UploadRecoveryRepository, storage: SourceStorage
    ) -> None:
        self._repository = repository
        self._storage = storage

    async def recover(
        self, attempt: SourceAttempt, parsed_data: dict[str, object]
    ) -> RecoveryResult:
        # First settle any in-flight database save. Do not delete a completed one.
        try:
            decision = await self._repository.begin(attempt, parsed_data)
        except SourceUnauthorized:
            return RecoveryResult(status="pending", reason="auth_required")
        except (SourceUnavailable, SourceConflict):
            return RecoveryResult(status="pending", reason="reconciliation_required")

        if decision.state == "completed":
            return RecoveryResult(status="completed", receipt=decision.receipt)
        if decision.state == "conflict":
            return RecoveryResult(status="pending", reason="state_conflict")

        # The failed/absent state blocks new source inserts and finalization.
        try:
            await self._storage.remove(attempt)
        except SourceUnauthorized:
            return RecoveryResult(status="pending", reason="auth_required")
        except (SourceUnavailable, SourceConflict, SourceTooLarge):
            return RecoveryResult(status="pending", reason="cleanup_required")

        # Even an empty DELETE receipt needs a database check before metadata goes.
        try:
            await self._repository.release(attempt)
        except SourceUnauthorized:
            return RecoveryResult(status="pending", reason="auth_required")
        except (SourceUnavailable, SourceConflict):
            return RecoveryResult(status="pending", reason="cleanup_required")
        return RecoveryResult(status="cleaned")
