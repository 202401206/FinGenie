"""Typed public dashboard values, with exact JSON numbers and source evidence."""

from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

import simplejson
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.analysis_responses import (
    AnalysisMetric,
    AnalysisSourceRef,
    MetricValue,
    WorkspaceAnalysisResponse,
)
from app.schemas.common import DocumentType

ExactValue = Annotated[
    MetricValue,
    BeforeValidator(AnalysisMetric.require_exact_number),
    Field(allow_inf_nan=False),
]


class DashboardMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str | None
    currency: str | None
    period_start: date | None
    period_end: date | None
    reporting_date: date | None
    unit_scale: Literal[1, 1000, 100000, 1000000, 10000000] | None


class DashboardPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: ExactValue | None
    reason: str | None
    source_refs: list[AnalysisSourceRef]

    @model_validator(mode="after")
    def explain_missing_value(self) -> Self:
        if self.value is None and not self.reason:
            raise ValueError("A missing chart value requires an explanation.")
        return self


class DashboardSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    points: list[DashboardPoint]


class DashboardChart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    unit: str
    status: Literal["available", "unavailable"]
    reason: str | None
    series: list[DashboardSeries]

    @model_validator(mode="after")
    def check_availability(self) -> Self:
        if self.status == "unavailable" and (not self.reason or self.series):
            raise ValueError("An unavailable chart requires a reason and no series.")
        if self.status == "available" and not self.series:
            raise ValueError("An available chart requires a series.")
        return self


class DashboardEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: ExactValue = Field(gt=0)
    unit: str
    date: date
    description: str
    source_refs: list[AnalysisSourceRef]


class WorkspaceDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    document_id: UUID
    document_type: DocumentType
    metadata: DashboardMetadata
    analysis: WorkspaceAnalysisResponse
    charts: list[DashboardChart]
    largest_inflows: list[DashboardEntry] = Field(max_length=5)
    largest_outflows: list[DashboardEntry] = Field(max_length=5)

    @model_validator(mode="after")
    def check_document_identity(self) -> Self:
        if (
            self.analysis.workspace_id != self.workspace_id
            or self.analysis.document_type != self.document_type
        ):
            raise ValueError("Dashboard analysis must match its owned workspace.")
        references = [
            ref for metric in self.analysis.metrics for ref in metric.source_refs
        ]
        references += [
            ref
            for chart in self.charts
            for series in chart.series
            for point in series.points
            for ref in point.source_refs
        ]
        references += [
            ref
            for item in self.largest_inflows + self.largest_outflows
            for ref in item.source_refs
        ]
        if any(ref.document_id != self.document_id for ref in references):
            raise ValueError("Dashboard evidence must match its saved document.")
        if self.document_type == DocumentType.BALANCE_SHEET and (
            self.largest_inflows or self.largest_outflows
        ):
            raise ValueError("Balance sheets have no bank flow rankings.")
        return self

    def to_wire_json(self) -> str:
        return simplejson.dumps(
            self.model_dump(mode="python"),
            use_decimal=True,
            allow_nan=False,
            default=str,
        )
