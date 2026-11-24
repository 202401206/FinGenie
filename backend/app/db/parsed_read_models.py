"""Internal parsed-document results, not public API response schemas."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.db.models import WorkspaceRecord
from app.db.parsed_models import ParsedBankStatement, ParsedSourceMetadata


def require_exact_number(value: object) -> object:
    if isinstance(value, (float, bool)):
        raise ValueError("Use exact amounts, not floats or booleans.")
    return value


ExactAmount = Annotated[
    Decimal, BeforeValidator(require_exact_number), Field(allow_inf_nan=False)
]


class ParsedBalanceItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    canonical_field: str | None
    raw_label: str
    value: ExactAmount | None
    source_row: int = Field(strict=True, gt=0)


class ParsedBalanceSection(BaseModel):
    model_config = ConfigDict(extra="allow")

    current: list[ParsedBalanceItem]
    non_current: list[ParsedBalanceItem]
    total: ExactAmount | None


class ParsedEquity(BaseModel):
    model_config = ConfigDict(extra="allow")

    share_capital: ExactAmount | None
    retained_earnings: ExactAmount | None
    total: ExactAmount | None


class ParsedBalanceSheet(BaseModel):
    """Validate the agreed stored contract without parsing or scaling amounts."""

    model_config = ConfigDict(extra="allow")

    company: str | None
    reporting_date: date
    currency: str | None = Field(pattern=r"^[A-Z]{3}$")
    unit_scale: (
        Annotated[
            Literal[1, 1000, 100000, 1000000, 10000000],
            BeforeValidator(require_exact_number),
        ]
        | None
    )
    assets: ParsedBalanceSection
    liabilities: ParsedBalanceSection
    equity: ParsedEquity
    unmapped: list[dict[str, object]]
    source_metadata: ParsedSourceMetadata
    source_locations: dict[str, object] = Field(default_factory=dict)


@dataclass(frozen=True)
class ParsedDocumentContext:
    workspace: WorkspaceRecord
    document_id: UUID
    parsed_json: ParsedBankStatement | ParsedBalanceSheet


class StoredParsedDocument(BaseModel):
    """Columns used only by the internal reader."""

    id: UUID
    workspace_id: UUID
    status: Literal["uploaded", "parsed", "failed"]
    parsed_json: dict[str, object] | None
