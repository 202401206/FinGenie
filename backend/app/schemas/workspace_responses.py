"""Public workspace responses, separate from database read models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import DocumentType, UserType


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    user_type: UserType
    document_type: DocumentType
    created_at: datetime


class WorkspacePageResponse(BaseModel):
    items: list[WorkspaceResponse]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)
