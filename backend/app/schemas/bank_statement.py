"""Bank statement Pydantic schemas adhering to contracts/examples/bank-statement.json."""

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SourceMetadata(BaseModel):
    """Metadata identifying the source document and worksheet."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    sheet_name: str | None = None


class SourceLocation(BaseModel):
    """1-based row reference for a scalar metadata field."""

    model_config = ConfigDict(extra="forbid")

    source_row: Annotated[
        int, Field(gt=0, description="1-based original row reference")
    ]


class UnmappedItem(BaseModel):
    """Preserves unrecognized source rows or metadata for auditability."""

    model_config = ConfigDict(extra="forbid")

    source_row: Annotated[
        int, Field(gt=0, description="1-based original row/record reference")
    ]
    raw_label: str
    raw_value: str
    reason: str


class BankTransaction(BaseModel):
    """Standardized single transaction row."""

    model_config = ConfigDict(extra="forbid")

    date: date
    description: Annotated[
        str, Field(min_length=1, description="Transaction description or narrative")
    ]
    debit: Annotated[
        Decimal,
        Field(ge=0, allow_inf_nan=False, description="Non-negative debit magnitude"),
    ]
    credit: Annotated[
        Decimal,
        Field(ge=0, allow_inf_nan=False, description="Non-negative credit magnitude"),
    ]
    balance: Annotated[
        Decimal,
        Field(allow_inf_nan=False, description="Account balance, may be negative"),
    ]
    source_row: Annotated[
        int, Field(gt=0, description="1-based original CSV record or spreadsheet row")
    ]


# Alias for convenience where Transaction is used
Transaction = BankTransaction


class BankStatement(BaseModel):
    """Full standardized bank statement model matching contracts/examples/bank-statement.json."""

    model_config = ConfigDict(extra="forbid")

    bank: str | None = None
    account_holder: str | None = None
    account_type: str | None = None
    currency: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    opening_balance: Annotated[
        Decimal | None, Field(default=None, allow_inf_nan=False)
    ] = None
    closing_balance: Annotated[
        Decimal | None, Field(default=None, allow_inf_nan=False)
    ] = None
    transactions: list[BankTransaction]
    unmapped: list[UnmappedItem] = Field(default_factory=list)
    source_metadata: SourceMetadata
    source_locations: dict[str, SourceLocation] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        if value is not None:
            code = value.strip().upper()
            if len(code) != 3 or not code.isalpha():
                raise ValueError(
                    f"Currency must be a 3-letter uppercase ISO code, got '{value}'"
                )
            return code
        return None

    @model_validator(mode="after")
    def validate_period_dates(self) -> "BankStatement":
        if self.period_start is not None and self.period_end is not None:
            if self.period_start > self.period_end:
                raise ValueError(
                    f"period_start ({self.period_start}) cannot be after period_end ({self.period_end})"
                )
        return self
