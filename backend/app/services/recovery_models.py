"""Internal recovery results. A cleaned failure is not a successful upload."""

from typing import Literal

from pydantic import BaseModel, model_validator

from app.db.parsed_models import ParsedSaveReceipt


class RecoveryDecision(BaseModel):
    state: Literal["completed", "failed", "absent", "conflict"]
    receipt: ParsedSaveReceipt | None = None

    @model_validator(mode="after")
    def check_receipt(self) -> "RecoveryDecision":
        if (self.state == "completed") != (self.receipt is not None):
            raise ValueError("Only a confirmed completed save has a receipt.")
        return self


class RecoveryResult(BaseModel):
    status: Literal["completed", "cleaned", "pending"]
    receipt: ParsedSaveReceipt | None = None
    reason: (
        Literal[
            "auth_required",
            "reconciliation_required",
            "cleanup_required",
            "state_conflict",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def check_result(self) -> "RecoveryResult":
        if (self.status == "completed") != (self.receipt is not None):
            raise ValueError("Only a completed upload has a success receipt.")
        if (self.status == "pending") != (self.reason is not None):
            raise ValueError("Pending recovery needs a reason.")
        return self
