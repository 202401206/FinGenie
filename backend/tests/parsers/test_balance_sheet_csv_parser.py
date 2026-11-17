"""Unit tests for Layout A balance sheet CSV parser."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from app.parsers.balance_sheet import parse_balance_sheet
from app.parsers.balance_sheet.csv_parser import parse_balance_sheet_csv
from app.parsers.errors import (
    InvalidStatementError,
    ResourceLimitError,
    UnsupportedFormatError,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CONTRACTS_EXAMPLE = (
    Path(__file__).parents[3] / "contracts" / "examples" / "balance-sheet.json"
)
TEST_DOC_ID = UUID("10000000-0000-4000-8000-000000000002")


class TestLayoutACSVParserSuccess:
    """Verifies successful parsing of valid Layout A CSV statements."""

    def test_parse_synthetic_layout_a_fixture(self) -> None:
        """Ensures synthetic_balance_sheet_layout_a.csv parses and matches expected JSON."""
        csv_path = FIXTURES_DIR / "synthetic_balance_sheet_layout_a.csv"
        with open(csv_path, "rb") as f:
            content = f.read()

        bs = parse_balance_sheet_csv(content, document_id=TEST_DOC_ID)

        # Expected json comparison
        json_path = FIXTURES_DIR / "synthetic_balance_sheet_layout_a.json"
        with open(json_path, "r", encoding="utf-8") as f:
            expected = json.load(f)

        assert bs.company == expected["company"]
        assert str(bs.reporting_date) == expected["reporting_date"]
        assert bs.currency == expected["currency"]
        assert bs.unit_scale == expected["unit_scale"]

        # Current Assets
        assert len(bs.assets.current) == len(expected["assets"]["current"])
        assert bs.assets.current[0].canonical_field == "cash"
        assert bs.assets.current[0].value == Decimal("100")
        assert bs.assets.current[0].source_row == 6

        assert bs.assets.current[1].canonical_field == "receivables"
        assert bs.assets.current[1].value == Decimal("50")
        assert bs.assets.current[1].source_row == 7

        # Non-Current Assets
        assert len(bs.assets.non_current) == len(expected["assets"]["non_current"])
        assert bs.assets.non_current[0].canonical_field == "property_plant_equipment"
        assert bs.assets.non_current[0].value == Decimal("150")
        assert bs.assets.non_current[0].source_row == 9

        # Assets Total
        assert bs.assets.total == Decimal("300")
        assert bs.source_locations["assets.total"].source_row == 10

        # Liabilities
        assert len(bs.liabilities.current) == 1
        assert bs.liabilities.current[0].canonical_field == "trade_payables"
        assert bs.liabilities.current[0].value == Decimal("80")
        assert bs.liabilities.current[0].source_row == 12

        assert len(bs.liabilities.non_current) == 1
        assert bs.liabilities.non_current[0].canonical_field == "long_term_borrowings"
        assert bs.liabilities.non_current[0].value == Decimal("40")
        assert bs.liabilities.non_current[0].source_row == 15

        assert bs.liabilities.total == Decimal("120")
        assert bs.source_locations["liabilities.total"].source_row == 16

        # Equity
        assert bs.equity.share_capital == Decimal("150")
        assert bs.equity.retained_earnings == Decimal("30")
        assert bs.equity.total == Decimal("180")
        assert bs.source_locations["equity.share_capital"].source_row == 18
        assert bs.source_locations["equity.retained_earnings"].source_row == 19
        assert bs.source_locations["equity.total"].source_row == 20

        # Document ID preserved unchanged
        assert bs.source_metadata.document_id == TEST_DOC_ID
        assert bs.source_metadata.sheet_name is None

    def test_utf8_bom_support(self) -> None:
        """Verifies that UTF-8 files with byte order mark (BOM) parse identically."""
        csv_path = FIXTURES_DIR / "synthetic_balance_sheet_layout_a.csv"
        with open(csv_path, "r", encoding="utf-8") as f:
            text = f.read()

        bom_bytes = text.encode("utf-8-sig")
        bs = parse_balance_sheet(bom_bytes, file_kind="csv", document_id=TEST_DOC_ID)
        assert bs.company == "Synthetic Demo Company"
        assert bs.reporting_date == date(2026, 1, 31)
        assert bs.assets.total == Decimal("300")

    def test_unbalanced_balance_sheet_parsed_unchanged(self) -> None:
        """An unbalanced balance sheet is parsed faithfully without parser repair."""
        csv_text = """Company: Unbalanced Co
Reporting Date: 2026-01-31
Currency: INR,Scale: Units
Particulars,Amount
Current Assets,
Cash,500
Total Assets,500
Current Liabilities,
Payables,100
Total Liabilities,100
Equity,
Share Capital,200
Total Equity,200
"""
        bs = parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)
        assert bs.assets.total == Decimal("500")
        assert bs.liabilities.total == Decimal("100")
        assert bs.equity.total == Decimal("200")
        # 500 != 100 + 200, parsed unchanged!

    def test_negative_retained_earnings_accumulated_losses(self) -> None:
        """Negative equity values (accumulated deficit) with minus or parentheses parse cleanly."""
        csv_text = """Reporting Date: 2026-01-31
Particulars,Amount
Equity,
Share Capital,1000
Retained Earnings,(250)
Total Equity,750
"""
        bs = parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)
        assert bs.equity.share_capital == Decimal("1000")
        assert bs.equity.retained_earnings == Decimal("-250")
        assert bs.equity.total == Decimal("750")

    def test_missing_optional_metadata(self) -> None:
        """Omitting company, scale, or currency keeps them as None."""
        csv_text = """Reporting Date: 2026-01-31
Particulars,Amount
Current Assets,
Cash,100
"""
        bs = parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)
        assert bs.company is None
        assert bs.currency is None
        assert bs.unit_scale is None
        assert bs.reporting_date == date(2026, 1, 31)
        assert len(bs.assets.current) == 1
        assert bs.assets.current[0].value == Decimal("100")

    def test_ambiguous_currency_and_scale_recorded_in_unmapped(self) -> None:
        """Ambiguous currency ($ / Rs.) or unknown scale is preserved in unmapped."""
        csv_text = """Reporting Date: 2026-01-31
Currency: $,Scale: Lacs
Particulars,Amount
Current Assets,
Cash,100
"""
        bs = parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)
        assert bs.currency is None
        assert bs.unit_scale is None
        reasons = [u.reason for u in bs.unmapped]
        assert "ambiguous_currency" in reasons
        assert "ambiguous_unit_scale" in reasons

    def test_reported_subtotals_preserved_in_unmapped(self) -> None:
        """Intermediate section subtotals are never counted as leaf items."""
        csv_text = """Reporting Date: 2026-01-31
Particulars,Amount
Current Assets,
Cash,100
Total Current Assets,100
Total Assets,100
"""
        bs = parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)
        # Cash is leaf item
        assert len(bs.assets.current) == 1
        assert bs.assets.current[0].canonical_field == "cash"
        assert bs.assets.total == Decimal("100")

        # Total Current Assets goes to unmapped
        subtotals = [u for u in bs.unmapped if u.reason == "reported_subtotal"]
        assert len(subtotals) == 1
        assert subtotals[0].raw_label == "Total Current Assets"
        assert subtotals[0].raw_value == "100"

    def test_unrecognized_financial_items_and_notes(self) -> None:
        """Unrecognized items under sections go to unmapped with proper reason codes."""
        csv_text = """Reporting Date: 2026-01-31
Note: All figures are unaudited
Particulars,Amount
Current Assets,
Cash,100
Cryptocurrency Reserve,50
Non-Current Assets,
Explanatory note on depreciation,
Equipment,200
Total Assets,350
"""
        bs = parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)
        assert len(bs.assets.current) == 1  # Only cash
        assert len(bs.assets.non_current) == 1  # Only equipment

        unrecognized_items = [
            u for u in bs.unmapped if u.reason == "unrecognized_financial_item"
        ]
        assert len(unrecognized_items) == 1
        assert unrecognized_items[0].raw_label == "Cryptocurrency Reserve"
        assert unrecognized_items[0].raw_value == "50"

        notes = [u for u in bs.unmapped if u.reason == "unrecognized_note"]
        assert any(
            "unaudited" in (n.raw_label + " " + n.raw_value).lower() for n in notes
        )


class TestLayoutACSVParserErrorsAndLimits:
    """Verifies that invalid statements, formulas, and limit violations raise proper errors."""

    def test_empty_content_raises_invalid_statement(self) -> None:
        """Empty CSV raises InvalidStatementError."""
        with pytest.raises(InvalidStatementError, match="empty"):
            parse_balance_sheet_csv(b"", document_id=TEST_DOC_ID)

        with pytest.raises(InvalidStatementError, match="empty"):
            parse_balance_sheet_csv(b"   \n\r\n  ", document_id=TEST_DOC_ID)

    def test_missing_table_header_raises_unsupported_format(self) -> None:
        """CSV without Particulars,Amount header raises UnsupportedFormatError."""
        content = b"Some Company\n2026-01-31\nNo valid headers here\n1,2,3"
        with pytest.raises(UnsupportedFormatError, match="table header"):
            parse_balance_sheet_csv(content, document_id=TEST_DOC_ID)

    def test_missing_reporting_date_raises_invalid_statement(self) -> None:
        """Statement without reporting date raises InvalidStatementError."""
        csv_text = """Company: No Date Corp
Particulars,Amount
Current Assets,
Cash,100
"""
        with pytest.raises(InvalidStatementError, match="reporting date"):
            parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)

    def test_invalid_reporting_date_format_raises_error(self) -> None:
        """Unparseable reporting date raises InvalidStatementError."""
        csv_text = """Reporting Date: 31st of Jan 2026
Particulars,Amount
Cash,100
"""
        with pytest.raises(InvalidStatementError, match="Invalid reporting date"):
            parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)

    def test_formula_cell_strictly_rejected(self) -> None:
        """Formula cells starting with = raise InvalidStatementError."""
        csv_text = """Reporting Date: 2026-01-31
Particulars,Amount
Current Assets,
Cash,=SUM(B5:B6)
"""
        with pytest.raises(InvalidStatementError, match="Formula found"):
            parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)

    def test_bad_numeric_amount_raises_error(self) -> None:
        """Malformed numeric amount raises InvalidStatementError."""
        csv_text = """Reporting Date: 2026-01-31
Particulars,Amount
Current Assets,
Cash,INVALID_100_XYZ
"""
        with pytest.raises(InvalidStatementError, match="Invalid numeric value"):
            parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)

    def test_unsupported_currency_raises_error(self) -> None:
        """Explicit unsupported currency raises InvalidStatementError."""
        csv_text = """Reporting Date: 2026-01-31
Currency: EUR
Particulars,Amount
Cash,100
"""
        with pytest.raises(
            InvalidStatementError, match="Unsupported balance sheet currency"
        ):
            parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)

    def test_layout_b_detected_parses_successfully(self) -> None:
        """Layout B (dated columns) is recognized and parsed successfully."""
        csv_text = """Reporting Date: 2026-03-31
Particulars,Note No,2026-03-31,2025-03-31
Current Assets,,,
Cash,,500,450
"""
        bs = parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)
        assert bs.reporting_date == date(2026, 3, 31)
        assert bs.assets.current[0].value == Decimal("500")

    def test_file_size_limit_exceeded(self) -> None:
        """Files exceeding 5 MiB raise ResourceLimitError."""
        oversized = b"Particulars,Amount\n" + b"Cash,100\n" * (6 * 1024 * 1024 // 9)
        with pytest.raises(ResourceLimitError, match="File size"):
            parse_balance_sheet_csv(oversized, document_id=TEST_DOC_ID)

    def test_row_limit_exceeded(self) -> None:
        """Files exceeding 20,000 rows raise ResourceLimitError."""
        rows = ["Particulars,Amount"] + ["Cash,100"] * 20_005
        content = "\n".join(rows).encode("utf-8")
        with pytest.raises(ResourceLimitError, match="row count"):
            parse_balance_sheet_csv(content, document_id=TEST_DOC_ID)

    def test_column_limit_exceeded(self) -> None:
        """Rows exceeding 50 columns raise ResourceLimitError."""
        wide_row = ",".join(["Cash"] * 55)
        content = f"Reporting Date: 2026-01-31\nParticulars,Amount\n{wide_row}".encode(
            "utf-8"
        )
        with pytest.raises(ResourceLimitError, match="column count"):
            parse_balance_sheet_csv(content, document_id=TEST_DOC_ID)

    def test_dispatch_entrypoint_file_kind(self) -> None:
        """parse_balance_sheet dispatches csv, rejects xlsx until D4, and rejects other kinds."""
        csv_text = """Reporting Date: 2026-01-31
Particulars,Amount
Current Assets,
Cash,100
"""
        bs = parse_balance_sheet(
            csv_text.encode("utf-8"), file_kind="csv", document_id=TEST_DOC_ID
        )
        assert bs.reporting_date == date(2026, 1, 31)

        # Invalid XLSX archive content
        with pytest.raises(
            UnsupportedFormatError, match="not a valid XLSX workbook archive"
        ):
            parse_balance_sheet(b"fake xlsx", file_kind="xlsx", document_id=TEST_DOC_ID)

        # Unsupported kind
        with pytest.raises(UnsupportedFormatError, match="Unsupported file kind"):
            parse_balance_sheet(b"fake pdf", file_kind="pdf", document_id=TEST_DOC_ID)
