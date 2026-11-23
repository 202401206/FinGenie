"""Manual recovery reads durable context; it never replays an upload or a token."""

from uuid import UUID

from app.db.repositories.upload_attempts import UploadAttemptRepository
from app.db.repositories.upload_recovery import UploadRecoveryRepository
from app.services.recovery_models import RecoveryResult
from app.services.source_errors import (
    SourceConflict,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.source_models import SourceAttempt
from app.services.source_storage import SourceStorage
from app.services.upload_attempt_models import StoredUploadAttempt, UploadAttemptSummary
from app.services.upload_recovery import UploadRecoveryService


class JournalRecoveryRepository:
    """Use the journal's locked decision with the existing cleanup workflow."""

    def __init__(self, journal, record, recovery):
        self.journal = journal
        self.record = record
        self.recovery = recovery

    async def begin(self, attempt, parsed_data):
        if attempt != self.record.attempt or parsed_data != self.record.parsed_data:
            raise ValueError("Recovery must use the stored attempt context.")
        return await self.journal.begin_recovery(self.record)

    async def release(self, attempt):
        return await self.recovery.release(attempt)


class UploadAttemptService:
    def __init__(
        self,
        journal: UploadAttemptRepository,
        recovery: UploadRecoveryRepository,
        storage: SourceStorage,
    ):
        self.journal = journal
        self.recovery = recovery
        self.storage = storage

    async def prepare(
        self,
        attempt: SourceAttempt,
        parsed_data: dict[str, object],
        *,
        attempt_id: UUID,
    ) -> UploadAttemptSummary:
        # Call before reserve/upload/finalize. A failed/unknown response stops writes.
        return await self.journal.create(attempt, parsed_data, attempt_id=attempt_id)

    async def confirm_completed(self, attempt_id: UUID) -> UploadAttemptSummary:
        # The database independently checks the original expected snapshot/source.
        return await self.journal.settle(attempt_id, revision=0, status="completed")

    async def recover(self, attempt_id: UUID) -> RecoveryResult:
        record: StoredUploadAttempt = await self.journal.get(attempt_id)
        service = UploadRecoveryService(
            JournalRecoveryRepository(self.journal, record, self.recovery), self.storage
        )
        result = await service.recover(record.attempt, record.parsed_data)
        status = "needs_review" if result.reason == "state_conflict" else result.status
        # Do not overwrite a previously verified terminal state with a transient failure.
        if (
            record.summary.status in ("completed", "cleaned", "needs_review")
            and status == "pending"
        ):
            return result
        try:
            settled = await self.journal.settle(
                attempt_id,
                revision=record.revision,
                status=status,
                error_code=result.reason,
            )
        except SourceUnauthorized:
            return RecoveryResult(status="pending", reason="auth_required")
        except (SourceUnavailable, SourceConflict):
            # Settlement may have committed despite the missing response. Recheck later.
            return RecoveryResult(status="pending", reason="reconciliation_required")
        if settled.status == "completed":
            return RecoveryResult(status="completed", receipt=settled.receipt)
        return result
