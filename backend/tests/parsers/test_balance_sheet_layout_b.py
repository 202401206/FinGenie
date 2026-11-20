"""Unit tests for Layout B comparative balance sheet CSV parser."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from app.parsers.balance_sheet import parse_balance_sheet
from app.parsers.balance_sheet.csv_parser import parse_balance_sheet_csv
from app.parsers.errors import InvalidStatementError

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_DOC_ID = UUID("20000000-0000-4000-8000-000000000001")


class TestLayoutBComparativeCSVParser:
    """Verifies parsing of Layout B comparative balance sheet CSV files."""

    def test_parse_synthetic_layout_b_fixture(self) -> None:
        """Ensures synthetic_balance_sheet_layout_b.csv matches synthetic_balance_sheet_layout_b.json."""
        csv_path = FIXTURES_DIR / "synthetic_balance_sheet_layout_b.csv"
        with open(csv_path, "rb") as f:
            content = f.read()

        bs = parse_balance_sheet_csv(content, document_id=TEST_DOC_ID)

        # Expected json comparison
        json_path = FIXTURES_DIR / "synthetic_balance_sheet_layout_b.json"
        with open(json_path, "r", encoding="utf-8") as f:
            expected = json.load(f)

        assert bs.company == expected["company"]
        assert str(bs.reporting_date) == expected["reporting_date"]
        assert bs.currency == expected["currency"]
        assert bs.unit_scale == expected["unit_scale"]

        # Current period assets (2026-03-31)
        assert len(bs.assets.current) == len(expected["assets"]["current"])
        assert bs.assets.current[0].canonical_field == "cash"
        assert bs.assets.current[0].value == Decimal("500")
        assert bs.assets.current[0].source_row == 6

        assert bs.assets.current[1].canonical_field == "receivables"
        assert bs.assets.current[1].value == Decimal("300")
        assert bs.assets.current[1].source_row == 7

        assert len(bs.assets.non_current) == 1
        assert bs.assets.non_current[0].canonical_field == "property_plant_equipment"
        assert bs.assets.non_current[0].value == Decimal("1200")
        assert bs.assets.non_current[0].source_row == 9

        assert bs.assets.total == Decimal("2000")
        assert bs.source_locations["assets.total"].source_row == 10

        # Current period liabilities
        assert len(bs.liabilities.current) == 1
        assert bs.liabilities.current[0].canonical_field == "trade_payables"
        assert bs.liabilities.current[0].value == Decimal("400")
        assert bs.liabilities.current[0].source_row == 12

        assert len(bs.liabilities.non_current) == 1
        assert bs.liabilities.non_current[0].canonical_field == "long_term_borrowings"
        assert bs.liabilities.non_current[0].value == Decimal("600")
        assert bs.liabilities.non_current[0].source_row == 14

        assert bs.liabilities.total == Decimal("1000")
        assert bs.source_locations["liabilities.total"].source_row == 15

        # Current period equity
        assert bs.equity.share_capital == Decimal("800")
        assert bs.equity.retained_earnings == Decimal("200")
        assert bs.equity.total == Decimal("1000")
        assert bs.source_locations["equity.share_capital"].source_row == 17
        assert bs.source_locations["equity.retained_earnings"].source_row == 18
        assert bs.source_locations["equity.total"].source_row == 19

        # Prior period values in unmapped (2025-03-31)
        prior_items = [u for u in bs.unmapped if u.reason == "prior_period_value"]
        assert len(prior_items) == 10

        prior_cash = next(
            u for u in prior_items if u.raw_label == "Cash and Cash Equivalents"
        )
        assert prior_cash.raw_value == "2025-03-31: 450"
        assert prior_cash.source_row == 6

        prior_total_assets = next(
            u for u in prior_items if u.raw_label == "Total Assets"
        )
        assert prior_total_assets.raw_value == "2025-03-31: 1830"
        assert prior_total_assets.source_row == 10

        prior_equity_total = next(
            u for u in prior_items if u.raw_label == "Total Equity"
        )
        assert prior_equity_total.raw_value == "2025-03-31: 900"
        assert prior_equity_total.source_row == 19

        # Preserved source metadata
        assert bs.source_metadata.document_id == TEST_DOC_ID
        assert bs.source_metadata.sheet_name is None

    def test_layout_b_reversed_period_columns(self) -> None:
        """Verifies that physical column order does not decide which period is current."""
        # Columns reversed: 2025-03-31 comes first, then 2026-03-31
        csv_text = """Company: Reversed Order Inc
Reporting Date: 2026-03-31
Currency: USD,Scale: Millions
Particulars,Note No,2025-03-31,2026-03-31
Current Assets,,,
Cash and Cash Equivalents,1,450,500
Total Assets,,1830,2000
"""
        bs = parse_balance_sheet(
            csv_text.encode("utf-8"), file_kind="csv", document_id=TEST_DOC_ID
        )

        # Must select 2026-03-31 as current
        assert bs.reporting_date == date(2026, 3, 31)
        assert bs.assets.current[0].value == Decimal("500")
        assert bs.assets.total == Decimal("2000")

        # 2025-03-31 is prior period in unmapped
        prior_items = [u for u in bs.unmapped if u.reason == "prior_period_value"]
        assert len(prior_items) == 2
        prior_cash = next(
            u for u in prior_items if u.raw_label == "Cash and Cash Equivalents"
        )
        assert prior_cash.raw_value == "2025-03-31: 450"

    def test_layout_b_without_note_column(self) -> None:
        """Layout B with optional Note No column omitted parses cleanly."""
        csv_text = """Company: No Note Corp
Reporting Date: 2026-03-31
Particulars,2026-03-31,2025-03-31
Current Assets,,
Cash,100,90
Total Assets,100,90
"""
        bs = parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)
        assert bs.assets.current[0].value == Decimal("100")
        assert bs.assets.total == Decimal("100")

        prior_items = [u for u in bs.unmapped if u.reason == "prior_period_value"]
        assert len(prior_items) == 2
        assert prior_items[0].raw_value == "2025-03-31: 90"

    def test_layout_b_note_numbers_never_treated_as_amounts(self) -> None:
        """Verifies that note numbers (e.g. 1, 2) are not parsed as financial values."""
        csv_text = """Reporting Date: 2026-03-31
Particulars,Note No,2026-03-31,2025-03-31
Current Assets,,,
Cash,1,100,90
Receivables,2,200,180
Total Assets,,300,270
"""
        bs = parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)
        # Values must be 100 and 200, NOT note numbers 1 or 2
        assert bs.assets.current[0].value == Decimal("100")
        assert bs.assets.current[1].value == Decimal("200")
        assert bs.assets.total == Decimal("300")

    def test_layout_b_missing_current_amount_keeps_none(self) -> None:
        """If current period amount is missing, value remains None without inventing zero."""
        csv_text = """Reporting Date: 2026-03-31
Particulars,Note No,2026-03-31,2025-03-31
Current Assets,,,
Cash,1,,90
Receivables,2,200,180
Total Assets,,200,270
"""
        bs = parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)
        assert bs.assets.current[0].canonical_field == "cash"
        assert bs.assets.current[0].value is None

        # Prior period still preserved
        prior_cash = next(u for u in bs.unmapped if u.raw_label == "Cash")
        assert prior_cash.raw_value == "2025-03-31: 90"
        assert prior_cash.reason == "prior_period_value"

    def test_layout_b_missing_reporting_date_column_rejected(self) -> None:
        """Declared reporting date not matching any table header column raises InvalidStatementError."""
        csv_text = """Reporting Date: 2026-03-31
Particulars,Note No,2024-03-31,2025-03-31
Cash,1,100,90
"""
        with pytest.raises(InvalidStatementError, match="Declared reporting date"):
            parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)

    def test_layout_b_duplicate_period_columns_rejected(self) -> None:
        """Duplicate period date columns in table header raise InvalidStatementError."""
        csv_text = """Reporting Date: 2026-03-31
Particulars,Note No,2026-03-31,2026-03-31
Cash,1,100,90
"""
        with pytest.raises(InvalidStatementError, match="Duplicate period"):
            parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)

    def test_layout_b_duplicate_year_columns_rejected(self) -> None:
        """Duplicate year columns in table header raise InvalidStatementError."""
        csv_text = """Reporting Date: 2026-03-31
Particulars,Note No,2026,2026
Cash,1,100,90
"""
        with pytest.raises(InvalidStatementError, match="Duplicate period"):
            parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)

    def test_layout_b_formula_in_prior_period_rejected(self) -> None:
        """Formulas in prior period amount cells are strictly rejected."""
        csv_text = """Reporting Date: 2026-03-31
Particulars,Note No,2026-03-31,2025-03-31
Current Assets,,,
Cash,1,100,=C6*0.9
"""
        with pytest.raises(InvalidStatementError, match="Formula found"):
            parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)

    def test_layout_b_unrecognized_financial_items(self) -> None:
        """Unrecognized financial items in Layout B preserve both current and prior amounts in unmapped."""
        csv_text = """Reporting Date: 2026-03-31
Particulars,Note No,2026-03-31,2025-03-31
Current Assets,,,
Cash,1,100,90
Cryptocurrency Reserve,2,50,40
Total Assets,,150,130
"""
        bs = parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)
        assert len(bs.assets.current) == 1  # Only cash

        # Unrecognized current item
        unrec = next(
            u
            for u in bs.unmapped
            if u.reason == "unrecognized_financial_item"
            and u.raw_label == "Cryptocurrency Reserve"
        )
        assert unrec.raw_value == "50"

        # Prior period value
        prior_crypto = next(
            u
            for u in bs.unmapped
            if u.reason == "prior_period_value"
            and u.raw_label == "Cryptocurrency Reserve"
        )
        assert prior_crypto.raw_value == "2025-03-31: 40"

    def test_layout_b_duplicate_period_dates_in_alternate_spellings_rejected(
        self,
    ) -> None:
        """Header with 2025-03-31 and 31/03/2025 has duplicate period identity and raises InvalidStatementError."""
        csv_text = """Reporting Date: 2026-03-31
Particulars,Note No,2026-03-31,2025-03-31,31/03/2025
Current Assets,,,,
Cash,1,100,90,90
"""
        with pytest.raises(
            InvalidStatementError, match="Duplicate period column '31/03/2025'"
        ):
            parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)

    def test_layout_b_ambiguous_year_and_date_overlap_rejected(self) -> None:
        """Header with both 2025 and 2025-03-31 cannot be disambiguated and raises InvalidStatementError."""
        csv_text = """Reporting Date: 2026-03-31
Particulars,Note No,2026-03-31,2025-03-31,2025
Current Assets,,,,
Cash,1,100,90,90
"""
        with pytest.raises(
            InvalidStatementError,
            match="Ambiguous overlapping period column '2025'",
        ):
            parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)

    def test_layout_b_unexpected_populated_column_header_rejected(self) -> None:
        """Unexpected populated column in header raises InvalidStatementError."""
        csv_text = """Reporting Date: 2026-03-31
Particulars,Note No,2026-03-31,2025-03-31,UnknownColumn
Current Assets,,,,,
Cash,1,100,90,10
"""
        with pytest.raises(
            InvalidStatementError,
            match="Unexpected populated column in table header: 'UnknownColumn'",
        ):
            parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)

    def test_layout_b_unexpected_populated_data_column_rejected(self) -> None:
        """Unexpected populated cell in unassigned column in data row raises InvalidStatementError."""
        csv_text = """Reporting Date: 2026-03-31
Particulars,Note No,2026-03-31,2025-03-31
Current Assets,,,
Cash,1,100,90,ExtraValue
"""
        with pytest.raises(
            InvalidStatementError,
            match="Unexpected populated cell in unassigned column 4",
        ):
            parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)

    def test_layout_b_tracked_empty_padding_columns_accepted(self) -> None:
        """Layout B with tracked empty padding columns parses properly."""
        csv_text = """Reporting Date: 2026-03-31
,Particulars,,Note No,,2026-03-31,,2025-03-31,
,Current Assets,,,,,,,
,Cash,,1,,100,,90,
,Total Assets,,,,100,,90,
"""
        bs = parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)
        assert bs.reporting_date == date(2026, 3, 31)
        assert bs.assets.current[0].value == Decimal("100")
        assert bs.assets.total == Decimal("100")
        prior_cash = next(u for u in bs.unmapped if u.raw_label == "Cash")
        assert prior_cash.raw_value == "2025-03-31: 90"

    def test_layout_b_current_period_blank_amount_with_prior_period_populated(
        self,
    ) -> None:
        """Current period blank amount preserves canonical LineItem with None, prior amount in unmapped."""
        csv_text = """Reporting Date: 2026-03-31
Particulars,Note No,2026-03-31,2025-03-31
Current Assets,,,
Cash,1,,450
Total Assets,,,450
"""
        bs = parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)
        assert len(bs.assets.current) == 1
        assert bs.assets.current[0].canonical_field == "cash"
        assert bs.assets.current[0].value is None
        assert bs.assets.current[0].source_row == 4

        assert bs.assets.total is None
        assert bs.source_locations["assets.total"].source_row == 5

        # Prior period values
        prior_items = [u for u in bs.unmapped if u.reason == "prior_period_value"]
        assert len(prior_items) == 2
        prior_cash = next(u for u in prior_items if u.raw_label == "Cash")
        assert prior_cash.raw_value == "2025-03-31: 450"

    def test_layout_b_note_column_not_treated_as_money(self) -> None:
        """Values in Note column (e.g. Note 1, 2) are not parsed as financial amounts."""
        csv_text = """Reporting Date: 2026-03-31
Particulars,Note No,2026-03-31,2025-03-31
Current Assets,,,
Cash,Note 1,500,450
Total Assets,,500,450
"""
        bs = parse_balance_sheet_csv(csv_text.encode("utf-8"), document_id=TEST_DOC_ID)
        assert bs.assets.current[0].value == Decimal("500")
        assert bs.assets.total == Decimal("500")
        # Ensure 'Note 1' was not parsed or added as an amount
        amounts = [bs.assets.current[0].value, bs.assets.total]
        assert Decimal("1") not in amounts
