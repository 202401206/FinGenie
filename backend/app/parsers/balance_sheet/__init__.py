"""Balance sheet parser package."""

from uuid import UUID

from app.parsers.balance_sheet.csv_parser import parse_balance_sheet_csv
from app.parsers.errors import UnsupportedFormatError
from app.schemas.balance_sheet import BalanceSheet

__all__ = ["BalanceSheet", "parse_balance_sheet"]


def parse_balance_sheet(
    content: bytes, *, file_kind: str, document_id: UUID
) -> BalanceSheet:
    """Entry point for parsing balance sheet files into standardized BalanceSheet.

    Args:
        content: Raw bytes of the uploaded balance sheet.
        file_kind: File type discriminator ('csv' or 'xlsx').
        document_id: UUID identifying the source document context.

    Returns:
        Validated BalanceSheet model.

    Raises:
        UnsupportedFormatError: If file_kind is unsupported or layout does not match.
        InvalidStatementError: If required fields or numeric structures are invalid.
        ResourceLimitError: If statement exceeds agreed bounds.
    """
    kind = file_kind.strip().lower()
    if kind == "csv":
        return parse_balance_sheet_csv(content, document_id=document_id)
    elif kind == "xlsx":
        raise UnsupportedFormatError(
            "XLSX balance sheet parsing is scheduled for Milestone D4"
        )
    else:
        raise UnsupportedFormatError(
            f"Unsupported file kind '{file_kind}'; expected 'csv' or 'xlsx'"
        )
