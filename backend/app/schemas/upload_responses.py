"""Public response for a confirmed bank-statement upload."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.workspace_responses import WorkspaceResponse


class UploadedDocumentResponse(BaseModel):
    id: UUID
    status: Literal["parsed"]


class UploadResponse(BaseModel):
    workspace: WorkspaceResponse
    document: UploadedDocumentResponse
