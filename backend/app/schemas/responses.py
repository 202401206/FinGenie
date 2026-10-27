"""Response models for implemented endpoints."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["fingenie-api"] = "fingenie-api"


class SourceRefModel(BaseModel):
    document_id: str
    sheet_name: str | None = None
    source_rows: list[int] = Field(default_factory=list)
    field_paths: list[str] = Field(default_factory=list)


class SummaryResponse(BaseModel):
    text: str
    calculation_ids: list[str] = Field(default_factory=list)
    source_refs: list[SourceRefModel] = Field(default_factory=list)
    disclaimer: str = "This is not financial advice."


class ChatResponse(BaseModel):
    text: str
    calculation_ids: list[str] = Field(default_factory=list)
    source_refs: list[SourceRefModel] = Field(default_factory=list)
    disclaimer: str = "This is not financial advice."
