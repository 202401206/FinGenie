"""Safe journal summaries and private, validated recovery context."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.parsed_models import ParsedSaveReceipt
from app.schemas.common import DocumentType
from app.services.source_models import SourceAttempt

AttemptStatus = Literal["pending", "completed", "cleaned", "needs_review"]
AttemptError = Literal[
    "auth_required", "reconciliation_required", "cleanup_required", "state_conflict"
]


class UploadAttemptSummary(BaseModel):
    """Last verified journal state. Current recovery checks the saved data again."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_id: UUID
    workspace_id: UUID
    document_id: UUID
    document_type: DocumentType
    status: AttemptStatus
    last_error_code: AttemptError | None = None
    receipt: ParsedSaveReceipt | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_state(self) -> "UploadAttemptSummary":
        if (self.status == "completed") != (self.receipt is not None):
            raise ValueError("Only a verified completed attempt has a receipt.")
        if (self.status == "needs_review") != (
            self.last_error_code == "state_conflict"
        ):
            raise ValueError("A conflicting attempt needs review.")
        if self.status in ("completed", "cleaned") and self.last_error_code is not None:
            raise ValueError("A settled attempt has no pending error.")
        if self.receipt is not None and (
            self.receipt.workspace_id != self.workspace_id
            or self.receipt.document_id != self.document_id
            or (
                self.document_type == DocumentType.BALANCE_SHEET
                and self.receipt.transaction_count != 0
            )
        ):
            raise ValueError("Journal receipt does not match its original IDs/type.")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("Journal timestamps must include their timezone.")
        return self


class StoredUploadAttempt(BaseModel):
    """Internal only: never serialize this model into an HTTP response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: UploadAttemptSummary
    attempt: SourceAttempt
    parsed_data: dict[str, object] = Field(repr=False)
    revision: int = Field(strict=True, ge=0)
