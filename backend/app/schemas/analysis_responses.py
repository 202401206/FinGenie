"""Public contract for analysis of a saved workspace."""

from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

import simplejson
from pydantic import BaseModel, Field, WithJsonSchema, field_validator, model_validator

from app.schemas.common import DocumentType
from app.schemas.responses import SourceRefModel

MetricValue = Annotated[
    Decimal, WithJsonSchema({"type": "number"}, mode="serialization")
]


class AnalysisSourceRef(SourceRefModel):
    document_id: UUID
    source_rows: list[Annotated[int, Field(strict=True, gt=0)]] = Field(
        default_factory=list
    )


class AnalysisMetric(BaseModel):
    key: str
    value: MetricValue | None = Field(allow_inf_nan=False)
    unit: str
    status: Literal["available", "unavailable"]
    reason: str | None
    calculation_id: str
    source_refs: list[AnalysisSourceRef]

    @field_validator("value", mode="before")
    @classmethod
    def require_exact_number(cls, value: object) -> object:
        if value is not None and type(value) not in (Decimal, int):
            raise ValueError("Metric values must be exact numbers.")
        return value

    @model_validator(mode="after")
    def check_availability(self) -> Self:
        if (self.status == "available") != (self.value is not None):
            raise ValueError("Only available metrics may have numeric values.")
        return self


class WorkspaceAnalysisResponse(BaseModel):
    workspace_id: UUID
    document_type: DocumentType
    currency: str | None
    reliability: Literal["valid", "unreliable", "insufficient_data"]
    metrics: list[AnalysisMetric]
    warnings: list[str]

    def to_wire_json(self) -> str:
        """Keep Decimal as JSON numbers and write UUIDs as strings."""
        return simplejson.dumps(
            self.model_dump(mode="python"),
            use_decimal=True,
            allow_nan=False,
            default=str,
        )
