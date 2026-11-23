"""Public error envelopes documented for the Sprint 2 API."""

from uuid import UUID

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    detail: ErrorDetail


class UploadErrorDetail(ErrorDetail):
    attempt_id: UUID | None = None


class UploadErrorResponse(BaseModel):
    detail: UploadErrorDetail
