"""Validate data at the save boundary. The parser keeps its own parsing models."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ParsedTransaction(BaseModel):
    model_config = ConfigDict(extra="allow")

    date: date
    description: str
    debit: Decimal = Field(ge=0, allow_inf_nan=False)
    credit: Decimal = Field(ge=0, allow_inf_nan=False)
    balance: Decimal = Field(allow_inf_nan=False)
    source_row: int = Field(strict=True, gt=0)

    @field_validator("debit", "credit", "balance", mode="before")
    @classmethod
    def require_exact_amount(cls, value: object) -> object:
        if isinstance(value, (float, bool)):
            raise ValueError("Use Decimal or integer amounts, not floats or booleans.")
        return value


class ParsedSourceMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    document_id: UUID
    sheet_name: str | None


class ParsedBankStatement(BaseModel):
    model_config = ConfigDict(extra="allow")

    bank: str | None
    account_holder: str | None
    account_type: str | None
    currency: str | None = Field(pattern=r"^[A-Z]{3}$")
    period_start: date | None
    period_end: date | None
    opening_balance: Decimal | None = Field(allow_inf_nan=False)
    closing_balance: Decimal | None = Field(allow_inf_nan=False)
    transactions: list[ParsedTransaction]
    unmapped: list[dict[str, object]]
    source_metadata: ParsedSourceMetadata
    source_locations: dict[str, object] = Field(default_factory=dict)

    @field_validator("opening_balance", "closing_balance", mode="before")
    @classmethod
    def require_exact_balance(cls, value: object) -> object:
        if isinstance(value, (float, bool)):
            raise ValueError("Use Decimal or integer balances, not floats or booleans.")
        return value

    @model_validator(mode="after")
    def check_period(self) -> "ParsedBankStatement":
        if (
            self.period_start
            and self.period_end
            and self.period_start > self.period_end
        ):
            raise ValueError("Period start must not be after period end.")
        return self


class ParsedSaveReceipt(BaseModel):
    workspace_id: UUID
    document_id: UUID
    status: Literal["parsed"]
    transaction_count: int = Field(strict=True, ge=0)
