"""Unit tests for the first supported bank CSV parser layout and edge cases."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from app.parsers.bank_statement import parse_bank_statement
from app.parsers.bank_statement.csv_parser import parse_bank_statement_csv
from app.parsers.errors import (
    InvalidStatementError,
    ResourceLimitError,
    UnsupportedFormatError,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DOC_ID = UUID("10000000-0000-4000-8000-000000000001")


class TestBankCSVParserLayout:
    """Verifies parsing of the first supported synthetic bank CSV layout."""

    def test_parse_standard_synthetic_csv(self) -> None:
        """Parses standard synthetic bank statement CSV and verifies exact contract parity."""
        csv_path = FIXTURES_DIR / "synthetic_bank_statement.csv"
        content = csv_path.read_bytes()

        statement = parse_bank_statement(content, file_kind="csv", document_id=DOC_ID)

        # Metadata assertions
        assert statement.bank == "Synthetic Demo Bank"
        assert statement.account_holder == "Synthetic Person"
        assert statement.account_type == "savings"
        assert statement.currency == "INR"
        assert statement.period_start == date(2026, 1, 1)
        assert statement.period_end == date(2026, 1, 31)
        assert statement.opening_balance == Decimal("10000")
        assert statement.closing_balance == Decimal("12500")

        # Source metadata
        assert statement.source_metadata.document_id == DOC_ID
        assert statement.source_metadata.sheet_name is None

        # Source locations for scalar metadata
        assert statement.source_locations["bank"].source_row == 1
        assert statement.source_locations["account_holder"].source_row == 2
        assert statement.source_locations["account_type"].source_row == 2
        assert statement.source_locations["currency"].source_row == 3
        assert statement.source_locations["period_start"].source_row == 3
        assert statement.source_locations["period_end"].source_row == 3
        assert statement.source_locations["opening_balance"].source_row == 4
        assert statement.source_locations["closing_balance"].source_row == 9

        # Transactions parity
        assert len(statement.transactions) == 3
        t1, t2, t3 = statement.transactions

        assert t1.date == date(2026, 1, 5)
        assert t1.description == "Synthetic salary"
        assert t1.debit == Decimal("0")
        assert t1.credit == Decimal("5000")
        assert t1.balance == Decimal("15000")
        assert t1.source_row == 6

        assert t2.date == date(2026, 1, 10)
        assert t2.description == "Synthetic rent"
        assert t2.debit == Decimal("2000")
        assert t2.credit == Decimal("0")
        assert t2.balance == Decimal("13000")
        assert t2.source_row == 7

        assert t3.date == date(2026, 1, 15)
        assert t3.description == "Synthetic groceries"
        assert t3.debit == Decimal("500")
        assert t3.credit == Decimal("0")
        assert t3.balance == Decimal("12500")
        assert t3.source_row == 8

        # Unmapped row preservation
        assert len(statement.unmapped) == 1
        unmapped_item = statement.unmapped[0]
        assert unmapped_item.source_row == 10
        assert unmapped_item.raw_label == "Unrecognized export note"
        assert unmapped_item.raw_value == "Synthetic note only"

    def test_utf8_with_bom_support(self) -> None:
        """Ensures statements exported with UTF-8 BOM are decoded without corrupting headers."""
        csv_path = FIXTURES_DIR / "synthetic_bank_statement.csv"
        raw_bytes = csv_path.read_bytes()
        bom_bytes = b"\xef\xbb\xbf" + raw_bytes

        statement = parse_bank_statement(bom_bytes, file_kind="csv", document_id=DOC_ID)
        assert statement.bank == "Synthetic Demo Bank"
        assert len(statement.transactions) == 3

    def test_multiline_and_quoted_records(self) -> None:
        """Verifies logical row counting when a CSV record contains quoted embedded newlines."""
        csv_path = FIXTURES_DIR / "synthetic_bank_statement_multiline.csv"
        content = csv_path.read_bytes()

        statement = parse_bank_statement(content, file_kind="csv", document_id=DOC_ID)
        assert len(statement.transactions) == 2

        # First transaction spans 2 physical lines, but is logical record 2
        t1 = statement.transactions[0]
        assert t1.source_row == 2
        assert "including bonus" in t1.description
        assert t1.credit == Decimal("6000.00")

        # Second transaction is logical record 3
        t2 = statement.transactions[1]
        assert t2.source_row == 3
        assert t2.description == "Rent"

    def test_blank_movement_fields(self) -> None:
        """In this supported layout, blank debit means 0, and blank credit means 0."""
        csv_path = FIXTURES_DIR / "synthetic_bank_statement_blank_movements.csv"
        content = csv_path.read_bytes()

        statement = parse_bank_statement(content, file_kind="csv", document_id=DOC_ID)
        assert len(statement.transactions) == 2

        t1, t2 = statement.transactions
        assert t1.debit == Decimal("0")
        assert t1.credit == Decimal("5000.00")

        assert t2.debit == Decimal("1200.00")
        assert t2.credit == Decimal("0")

    def test_negative_balance_support(self) -> None:
        """Supports negative balances with explicit minus sign or parentheses."""
        csv_data = (
            "Date,Description,Debit,Credit,Balance\n"
            "2026-01-01,Overdraft fee,50.00,,(150.00)\n"
            "2026-01-02,Interest,10.00,,-160.00\n"
        ).encode("utf-8")

        statement = parse_bank_statement(csv_data, file_kind="csv", document_id=DOC_ID)
        assert len(statement.transactions) == 2
        assert statement.transactions[0].balance == Decimal("-150.00")
        assert statement.transactions[1].balance == Decimal("-160.00")

    def test_zero_movements_statement(self) -> None:
        """Valid layout with zero transactions produces a valid empty statement."""
        csv_data = "Date,Description,Debit,Credit,Balance\n".encode("utf-8")
        statement = parse_bank_statement(csv_data, file_kind="csv", document_id=DOC_ID)
        assert len(statement.transactions) == 0


class TestBankCSVParserValidationErrors:
    """Verifies robust validation and rejection of invalid or malformed CSV statements."""

    def test_empty_content_rejected(self) -> None:
        """Empty byte content raises InvalidStatementError."""
        with pytest.raises(InvalidStatementError, match="empty"):
            parse_bank_statement(b"", file_kind="csv", document_id=DOC_ID)

        with pytest.raises(InvalidStatementError, match="empty"):
            parse_bank_statement(b"   \n\r  ", file_kind="csv", document_id=DOC_ID)

    def test_unsupported_encoding_rejected(self) -> None:
        """Non-UTF-8 bytes raise UnsupportedFormatError."""
        invalid_bytes = b"\xff\xfe\x00\x00Date,Description,Debit,Credit,Balance"
        with pytest.raises(UnsupportedFormatError, match="UTF-8"):
            parse_bank_statement(invalid_bytes, file_kind="csv", document_id=DOC_ID)

    def test_unsupported_headers_rejected(self) -> None:
        """Unrecognized table headers raise UnsupportedFormatError."""
        csv_path = FIXTURES_DIR / "synthetic_bank_statement_unsupported_headers.csv"
        content = csv_path.read_bytes()

        with pytest.raises(
            UnsupportedFormatError,
            match="could not locate required transaction table headers",
        ):
            parse_bank_statement(content, file_kind="csv", document_id=DOC_ID)

    def test_malformed_amount_raises_invalid_statement(self) -> None:
        """Non-numeric string in monetary column raises InvalidStatementError."""
        csv_data = "Date,Description,Debit,Credit,Balance\n2026-01-01,Test,NOT_AN_AMOUNT,0,100\n".encode(
            "utf-8"
        )
        with pytest.raises(InvalidStatementError, match="Invalid numeric value"):
            parse_bank_statement(csv_data, file_kind="csv", document_id=DOC_ID)

    def test_missing_both_movements_raises_invalid_statement(self) -> None:
        """A transaction row with neither debit nor credit is rejected."""
        csv_data = "Date,Description,Debit,Credit,Balance\n2026-01-01,No movement,,,100\n".encode(
            "utf-8"
        )
        with pytest.raises(InvalidStatementError, match="neither debit nor credit"):
            parse_bank_statement(csv_data, file_kind="csv", document_id=DOC_ID)

    def test_unsupported_file_kind_rejected(self) -> None:
        """Discriminator for unsupported file_kind raises UnsupportedFormatError."""
        csv_path = FIXTURES_DIR / "synthetic_bank_statement.csv"
        content = csv_path.read_bytes()

        with pytest.raises(UnsupportedFormatError, match="Unsupported file kind"):
            parse_bank_statement(content, file_kind="pdf", document_id=DOC_ID)

        with pytest.raises(
            UnsupportedFormatError, match="File is not a valid XLSX workbook archive"
        ):
            parse_bank_statement(content, file_kind="xlsx", document_id=DOC_ID)


class TestBankCSVParserResourceLimits:
    """Verifies that configured resource boundaries (size, rows, columns) are strictly enforced."""

    def test_file_size_exceeded(self) -> None:
        """Files exceeding 5 MiB are rejected before unbounded parsing."""
        oversized = b"a" * (5 * 1024 * 1024 + 1)
        with pytest.raises(ResourceLimitError, match="5 MiB"):
            parse_bank_statement(oversized, file_kind="csv", document_id=DOC_ID)

    def test_max_columns_exceeded(self) -> None:
        """Rows with more than 50 columns are rejected."""
        wide_row = ",".join([f"col{i}" for i in range(55)]) + "\n"
        with pytest.raises(ResourceLimitError, match="maximum allowed columns"):
            parse_bank_statement_csv(wide_row.encode("utf-8"), document_id=DOC_ID)

    def test_max_transactions_exceeded(self) -> None:
        """Statements with over 10,000 transactions are bounded."""
        header = "Date,Description,Debit,Credit,Balance\n"
        rows = "2026-01-01,Test payment,10,0,1000\n" * 10_001
        large_csv = (header + rows).encode("utf-8")

        with pytest.raises(
            ResourceLimitError, match="maximum allowed transaction limit"
        ):
            parse_bank_statement_csv(large_csv, document_id=DOC_ID)
