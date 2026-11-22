"""Unit tests for the second agreed bank statement export layout (Layout B) in CSV and XLSX."""

import io
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import openpyxl
import pytest

from app.parsers.bank_statement import parse_bank_statement
from app.parsers.errors import UnsupportedFormatError

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DOC_ID = UUID("20000000-0000-4000-8000-000000000002")


def _create_synthetic_layout_b_xlsx() -> bytes:
    """Helper building a deterministic in-memory XLSX workbook for Layout B."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Current Account Activity"

    # Preamble metadata (Rows 1-4)
    ws.append(["Bank: Commercial Apex Bank"])
    ws.append(["Account Holder: Global Trading Corp", "Account Type: current"])
    ws.append(["Currency: USD", "Statement Period: 01/01/2026 to 31/01/2026"])
    ws.append(["Opening Balance: 25000.00"])

    # Table Header (Row 5): Uses Layout B aliases and extra intermediate columns
    ws.append(
        [
            "Txn Date",
            "Value Date",
            "Particulars",
            "Chq/Ref No",
            "Withdrawal (Dr)",
            "Deposit (Cr)",
            "Net Balance",
        ]
    )

    # Transactions (Rows 6-8) with DD/MM/YYYY text dates and float amounts
    ws.append(
        [
            "05/01/2026",
            "05/01/2026",
            "Client invoice settlement",
            "REF10023",
            None,
            15000.00,
            40000.00,
        ]
    )
    ws.append(
        [
            "12/01/2026",
            "12/01/2026",
            "Office supplies vendor",
            "CHQ00987",
            3500.50,
            None,
            36499.50,
        ]
    )
    ws.append(
        [
            "25/01/2026",
            "25/01/2026",
            "Cloud hosting server",
            "TXN99481",
            499.50,
            None,
            36000.00,
        ]
    )

    # Footer and unmapped
    ws.append(["Closing Balance: 36000.00"])
    ws.append(["Notice: End of monthly statement summary"])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestBankLayoutBParser:
    """Verifies parsing of the second supported bank export layout (Layout B)."""

    def test_parse_layout_b_csv(self) -> None:
        """Verifies parsing of Layout B from CSV input."""
        csv_path = FIXTURES_DIR / "synthetic_bank_layout_b.csv"
        content = csv_path.read_bytes()

        statement = parse_bank_statement(content, file_kind="csv", document_id=DOC_ID)

        # Metadata assertions
        assert statement.bank == "Commercial Apex Bank"
        assert statement.account_holder == "Global Trading Corp"
        assert statement.account_type == "current"
        assert statement.currency == "USD"
        assert statement.period_start == date(2026, 1, 1)
        assert statement.period_end == date(2026, 1, 31)
        assert statement.opening_balance == Decimal("25000.00")
        assert statement.closing_balance == Decimal("36000.00")

        # Source metadata
        assert statement.source_metadata.document_id == DOC_ID
        assert statement.source_metadata.sheet_name is None

        # Source locations
        assert statement.source_locations["bank"].source_row == 1
        assert statement.source_locations["account_holder"].source_row == 2
        assert statement.source_locations["account_type"].source_row == 2
        assert statement.source_locations["currency"].source_row == 3
        assert statement.source_locations["period_start"].source_row == 3
        assert statement.source_locations["period_end"].source_row == 3
        assert statement.source_locations["opening_balance"].source_row == 4
        assert statement.source_locations["closing_balance"].source_row == 9

        # Transactions verification
        assert len(statement.transactions) == 3
        t1, t2, t3 = statement.transactions

        assert t1.date == date(2026, 1, 5)
        assert t1.description == "Client invoice settlement"
        assert t1.debit == Decimal("0")
        assert t1.credit == Decimal("15000.00")
        assert t1.balance == Decimal("40000.00")
        assert t1.source_row == 6

        assert t2.date == date(2026, 1, 12)
        assert t2.description == "Office supplies vendor"
        assert t2.debit == Decimal("3500.50")
        assert t2.credit == Decimal("0")
        assert t2.balance == Decimal("36499.50")
        assert t2.source_row == 7

        assert t3.date == date(2026, 1, 25)
        assert t3.description == "Cloud hosting server"
        assert t3.debit == Decimal("499.50")
        assert t3.credit == Decimal("0")
        assert t3.balance == Decimal("36000.00")
        assert t3.source_row == 8

        # Unmapped notice row
        assert len(statement.unmapped) == 1
        assert statement.unmapped[0].source_row == 10
        assert statement.unmapped[0].raw_label == "Notice"
        assert statement.unmapped[0].raw_value == "End of monthly statement summary"

    def test_parse_layout_b_xlsx(self) -> None:
        """Verifies parsing of Layout B from XLSX input."""
        xlsx_bytes = _create_synthetic_layout_b_xlsx()

        statement = parse_bank_statement(
            xlsx_bytes, file_kind="xlsx", document_id=DOC_ID
        )

        assert statement.bank == "Commercial Apex Bank"
        assert statement.account_holder == "Global Trading Corp"
        assert statement.account_type == "current"
        assert statement.currency == "USD"
        assert statement.period_start == date(2026, 1, 1)
        assert statement.period_end == date(2026, 1, 31)
        assert statement.opening_balance == Decimal("25000.00")
        assert statement.closing_balance == Decimal("36000.00")

        assert statement.source_metadata.sheet_name == "Current Account Activity"
        assert len(statement.transactions) == 3
        assert statement.transactions[0].credit == Decimal("15000.00")
        assert statement.transactions[1].debit == Decimal("3500.50")
        assert statement.transactions[2].balance == Decimal("36000.00")

    def test_layout_a_regression_preservation(self) -> None:
        """Confirms that adding Layout B support introduces zero regressions on Layout 1."""
        csv_path = FIXTURES_DIR / "synthetic_bank_statement.csv"
        content = csv_path.read_bytes()

        statement = parse_bank_statement(content, file_kind="csv", document_id=DOC_ID)
        assert statement.bank == "Synthetic Demo Bank"
        assert statement.currency == "INR"
        assert len(statement.transactions) == 3

    def test_conflicting_or_incomplete_headers_rejected(self) -> None:
        """Incomplete or non-matching headers fail explicitly rather than fuzzy guessing."""
        csv_data = (
            "Date,Particulars,Debit Amount\n2026-01-01,Incomplete headers,100.00\n"
        ).encode("utf-8")

        with pytest.raises(
            UnsupportedFormatError,
            match="could not locate required transaction table headers",
        ):
            parse_bank_statement(csv_data, file_kind="csv", document_id=DOC_ID)
