"""Balance sheet Pydantic schemas adhering to contracts/examples/balance-sheet.json."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_CURRENCIES: set[str] = {"INR", "USD"}
SUPPORTED_UNIT_SCALES: set[int] = {1, 1_000, 100_000, 1_000_000, 10_000_000}


def _reject_boolean_and_nonfinite(value: Any) -> Any:
    """Ensure financial amounts are not booleans or non-finite numbers."""
    if isinstance(value, bool):
        raise ValueError("Boolean values are not permitted for financial amounts")
    return value


class SourceMetadata(BaseModel):
    """Metadata identifying the source document and worksheet."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    sheet_name: str | None = None


class SourceLocation(BaseModel):
    """1-based row reference for a scalar metadata field."""

    model_config = ConfigDict(extra="forbid")

    source_row: Annotated[
        int, Field(strict=True, gt=0, description="1-based original row reference")
    ]


class UnmappedItem(BaseModel):
    """Preserves unrecognized source rows, metadata, or prior period values for auditability."""

    model_config = ConfigDict(extra="forbid")

    source_row: Annotated[
        int,
        Field(strict=True, gt=0, description="1-based original row/record reference"),
    ]
    raw_label: str
    raw_value: str
    reason: str


class LineItem(BaseModel):
    """Single balance sheet line item within an asset or liability section."""

    model_config = ConfigDict(extra="forbid")

    canonical_field: str
    raw_label: str
    value: Annotated[Decimal | None, Field(default=None, allow_inf_nan=False)] = None
    source_row: Annotated[
        int, Field(strict=True, gt=0, description="1-based original row reference")
    ]

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, v: Any) -> Any:
        return _reject_boolean_and_nonfinite(v)


class SectionItems(BaseModel):
    """Line items and reported subtotal/total for assets or liabilities."""

    model_config = ConfigDict(extra="forbid")

    current: list[LineItem] = Field(default_factory=list)
    non_current: list[LineItem] = Field(default_factory=list)
    total: Annotated[Decimal | None, Field(default=None, allow_inf_nan=False)] = None

    @field_validator("total", mode="before")
    @classmethod
    def validate_total(cls, v: Any) -> Any:
        return _reject_boolean_and_nonfinite(v)


class Equity(BaseModel):
    """Equity section holding share capital, retained earnings, and total."""

    model_config = ConfigDict(extra="forbid")

    share_capital: Annotated[
        Decimal | None, Field(default=None, allow_inf_nan=False)
    ] = None
    retained_earnings: Annotated[
        Decimal | None, Field(default=None, allow_inf_nan=False)
    ] = None
    total: Annotated[Decimal | None, Field(default=None, allow_inf_nan=False)] = None

    @field_validator("share_capital", "retained_earnings", "total", mode="before")
    @classmethod
    def validate_equity_amounts(cls, v: Any) -> Any:
        return _reject_boolean_and_nonfinite(v)


class BalanceSheet(BaseModel):
    """Full standardized balance sheet model matching contracts/examples/balance-sheet.json."""

    model_config = ConfigDict(extra="forbid")

    company: str | None = None
    reporting_date: date
    currency: str | None = None
    unit_scale: int | None = None
    assets: SectionItems
    liabilities: SectionItems
    equity: Equity
    unmapped: list[UnmappedItem] = Field(default_factory=list)
    source_metadata: SourceMetadata
    source_locations: dict[str, SourceLocation] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        if value is not None:
            code = value.strip().upper()
            if code not in SUPPORTED_CURRENCIES:
                raise ValueError(
                    f"Unsupported balance sheet currency '{value}'. Supported currencies: {sorted(SUPPORTED_CURRENCIES)}"
                )
            return code
        return None

    @field_validator("unit_scale", mode="before")
    @classmethod
    def validate_unit_scale(cls, value: Any) -> int | None:
        if value is not None:
            if isinstance(value, bool):
                raise ValueError("Boolean values are not permitted for unit_scale")
            if not isinstance(value, int):
                raise ValueError(
                    f"unit_scale must be an integer, got {type(value).__name__}"
                )
            if value not in SUPPORTED_UNIT_SCALES:
                raise ValueError(
                    f"Unsupported unit scale {value}. Allowed unit scales: {sorted(SUPPORTED_UNIT_SCALES)}"
                )
            return value
        return None
