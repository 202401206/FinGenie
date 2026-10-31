"""Typed database read results; HTTP response schemas belong to the API team."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import DocumentType, UserType

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    limit: int
    offset: int
    total: int


class WorkspaceRecord(BaseModel):
    id: UUID
    name: str
    user_type: UserType
    document_type: DocumentType
    created_at: datetime


class DocumentMetadata(BaseModel):
    id: UUID
    status: Literal["uploaded", "parsed", "failed"]
    original_filename: str
    currency: str | None
    period_start: date | None
    period_end: date | None


class WorkspaceDetails(BaseModel):
    workspace: WorkspaceRecord
    documents: list[DocumentMetadata]


class TransactionRecord(BaseModel):
    id: UUID
    document_id: UUID
    date: date
    description: str
    debit: Decimal = Field(ge=0, allow_inf_nan=False)
    credit: Decimal = Field(ge=0, allow_inf_nan=False)
    balance: Decimal = Field(allow_inf_nan=False)
    source_row: int = Field(gt=0)
