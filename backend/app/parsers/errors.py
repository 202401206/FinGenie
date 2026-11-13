"""Safe, structured parser exceptions independent of HTTP or database layers."""


class BankStatementParserError(Exception):
    """Base exception for all bank statement parser errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsupportedFormatError(BankStatementParserError):
    """Raised when the file format, extension, encoding, or layout is unsupported."""


class InvalidStatementError(BankStatementParserError):
    """Raised when a supported layout contains invalid, malformed, or missing required statement data."""


class AmbiguousWorksheetError(BankStatementParserError):
    """Raised when an XLSX workbook has multiple candidate sheets or no clear matching sheet."""


class ResourceLimitError(BankStatementParserError):
    """Raised when a statement exceeds agreed resource bounds (rows, columns, or uncompressed size)."""
