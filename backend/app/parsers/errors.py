"""Safe, structured parser exceptions independent of HTTP or database layers."""


class StatementParserError(Exception):
    """Base exception for all financial statement parser errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BankStatementParserError(StatementParserError):
    """Base exception for all bank statement parser errors."""


class BalanceSheetParserError(StatementParserError):
    """Base exception for all balance sheet parser errors."""


class UnsupportedFormatError(BankStatementParserError, BalanceSheetParserError):
    """Raised when the file format, extension, encoding, or layout is unsupported."""


class InvalidStatementError(BankStatementParserError, BalanceSheetParserError):
    """Raised when a supported layout contains invalid, malformed, or missing required statement data."""


class AmbiguousWorksheetError(BankStatementParserError, BalanceSheetParserError):
    """Raised when an XLSX workbook has multiple candidate sheets or no clear matching sheet."""


class ResourceLimitError(BankStatementParserError, BalanceSheetParserError):
    """Raised when a statement exceeds agreed resource bounds (rows, columns, or uncompressed size)."""
