"""Public contracts for viewing and recovering upload attempts."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.parsed_models import ParsedSaveReceipt
from app.services.upload_attempt_models import UploadAttemptSummary


class UploadAttemptPage(BaseModel):
    items: list[UploadAttemptSummary]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)


class RecoverUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UploadRecoveryResponse(BaseModel):
    attempt_id: UUID
    status: Literal["completed", "cleaned"]
    receipt: ParsedSaveReceipt | None = None
