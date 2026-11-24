"""Settings API values. Currency preferences never convert source amounts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

Currency = Literal["INR", "USD", "EUR", "GBP", "AED", "AUD", "CAD", "JPY"]
Theme = Literal["light", "dark"]


class UserPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_currency: Currency = "INR"
    theme: Theme = "light"


class PreferencesPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_currency: Currency | None = None
    theme: Theme | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if isinstance(value, dict) and any(item is None for item in value.values()):
            raise ValueError("Preference values cannot be null.")
        return value


class DataDeleted(BaseModel):
    status: Literal["deleted"] = "deleted"
