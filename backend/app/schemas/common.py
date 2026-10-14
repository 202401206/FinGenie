"""Shared vocabulary; upload eligibility validation belongs to a later sprint."""

from enum import StrEnum

from pydantic import BaseModel


class UserType(StrEnum):
    PERSONAL = "personal"
    BUSINESS = "business"


class DocumentType(StrEnum):
    BANK_STATEMENT = "bank_statement"
    BALANCE_SHEET = "balance_sheet"


class DocumentContext(BaseModel):
    user_type: UserType
    document_type: DocumentType
