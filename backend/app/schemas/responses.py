"""Response models for implemented endpoints."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["fingenie-api"] = "fingenie-api"


class CurrentUser(BaseModel):
    id: UUID
