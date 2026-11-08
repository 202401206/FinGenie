"""Bank statement parser package."""

from uuid import UUID

from app.parsers.bank_statement.csv_parser import parse_bank_statement_csv
from app.parsers.errors import UnsupportedFormatError
from app.schemas.bank_statement import BankStatement, BankTransaction

__all__ = ["BankStatement", "BankTransaction", "parse_bank_statement"]


def parse_bank_statement(
    content: bytes, *, file_kind: str, document_id: UUID
) -> BankStatement:
    """Entry point for parsing bank statement files into standardized BankStatement.

    Args:
        content: Raw bytes of the uploaded file.
        file_kind: File type discriminator ('csv' or 'xlsx').
        document_id: UUID identifying the source document context.

    Returns:
        Validated BankStatement model.

    Raises:
        UnsupportedFormatError: If file_kind is not supported or layout cannot be parsed.
        InvalidStatementError: If required fields or data types are invalid.
        ResourceLimitError: If statement exceeds row, column, or file size limits.
    """
    kind = file_kind.strip().lower()
    if kind == "csv":
        return parse_bank_statement_csv(content, document_id=document_id)
    elif kind == "xlsx":
        raise UnsupportedFormatError("XLSX parsing is scheduled for Milestone 3")
    else:
        raise UnsupportedFormatError(
            f"Unsupported file kind '{file_kind}'; expected 'csv' or 'xlsx'"
        )
