"""Public workspace responses, separate from database read models."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema, field_validator

from app.schemas.common import DocumentType, UserType
from app.services.source_models import SourceAttempt


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    user_type: UserType
    document_type: DocumentType
    created_at: datetime


class PageResponse(BaseModel):
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)


class WorkspacePageResponse(PageResponse):
    items: list[WorkspaceResponse]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: Literal["uploaded", "parsed", "failed"]
    original_filename: str
    currency: str | None
    period_start: date | None
    period_end: date | None

    @field_validator("original_filename")
    @classmethod
    def display_filename(cls, value: str) -> str:
        try:
            return str(SourceAttempt.sanitize_filename(value))
        except ValueError:
            # Older metadata may predate the upload filename checks.
            return "document"


class WorkspaceDetailsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workspace: WorkspaceResponse
    documents: list[DocumentResponse]


Money = Annotated[Decimal, WithJsonSchema({"type": "number"}, mode="serialization")]


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    date: date
    description: str
    debit: Money = Field(ge=0, allow_inf_nan=False)
    credit: Money = Field(ge=0, allow_inf_nan=False)
    balance: Money = Field(allow_inf_nan=False)
    source_row: int = Field(gt=0)


class TransactionPageResponse(PageResponse):
    items: list[TransactionResponse]
