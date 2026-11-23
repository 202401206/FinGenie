"""Unit tests for balance sheet XLSX parser across Layout A and Layout B."""

import io
import zipfile
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import openpyxl
import pytest

from app.parsers.balance_sheet import parse_balance_sheet
from app.parsers.balance_sheet.xlsx_parser import parse_balance_sheet_xlsx
from app.parsers.errors import (
    AmbiguousWorksheetError,
    InvalidStatementError,
    ResourceLimitError,
    UnsupportedFormatError,
)

TEST_DOC_ID = UUID("30000000-0000-4000-8000-000000000001")


def create_test_xlsx(
    sheets: dict[str, list[list[object]]],
) -> bytes:
    """Helper to create multi-sheet XLSX workbooks in memory."""
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    for title, rows in sheets.items():
        ws = wb.create_sheet(title=title)
        for r in rows:
            ws.append(r)

    stream = io.BytesIO()
    wb.save(stream)
    return stream.getvalue()


class TestBalanceSheetXLSXSuccess:
    """Verifies successful parsing of Layout A and Layout B XLSX spreadsheets."""

    def test_parse_layout_a_xlsx(self) -> None:
        """Tests Layout A single-period balance sheet in XLSX with sheet_name preservation."""
        rows = [
            ["Company: Synthetic Demo Company"],
            ["Reporting Date: 2026-01-31"],
            ["Currency: INR", "Scale: Lakhs"],
            ["Particulars", "Amount"],
            ["Current Assets", ""],
            ["Cash", 100],
            ["Receivables", 50],
            ["Non-Current Assets", ""],
            ["Equipment", 150],
            ["Total Assets", 300],
            ["Current Liabilities", ""],
            ["Payables", 80],
            ["Non-Current Liabilities", ""],
            ["Long-Term Borrowings", ""],
            ["Long-term loan", 40],
            ["Total Liabilities", 120],
            ["Equity", ""],
            ["Share Capital", 150],
            ["Retained Earnings", 30],
            ["Total Equity", 180],
        ]
        content = create_test_xlsx({"Balance Sheet": rows})
        bs = parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)

        assert bs.company == "Synthetic Demo Company"
        assert bs.reporting_date == date(2026, 1, 31)
        assert bs.currency == "INR"
        assert bs.unit_scale == 100000

        # Assets
        assert len(bs.assets.current) == 2
        assert bs.assets.current[0].canonical_field == "cash"
        assert bs.assets.current[0].value == Decimal("100")
        assert bs.assets.current[0].source_row == 6

        assert bs.assets.current[1].canonical_field == "receivables"
        assert bs.assets.current[1].value == Decimal("50")
        assert bs.assets.current[1].source_row == 7

        assert bs.assets.non_current[0].canonical_field == "property_plant_equipment"
        assert bs.assets.non_current[0].value == Decimal("150")
        assert bs.assets.total == Decimal("300")
        assert bs.source_locations["assets.total"].source_row == 10

        # Liabilities & Equity
        assert bs.liabilities.total == Decimal("120")
        assert bs.equity.total == Decimal("180")
        assert bs.equity.share_capital == Decimal("150")
        assert bs.equity.retained_earnings == Decimal("30")

        # Source metadata preserves sheet name
        assert bs.source_metadata.document_id == TEST_DOC_ID
        assert bs.source_metadata.sheet_name == "Balance Sheet"

    def test_parse_layout_b_xlsx(self) -> None:
        """Tests Layout B comparative balance sheet in XLSX with prior period preserved in unmapped."""
        rows = [
            ["Company: Global Synthetic Corp"],
            ["Reporting Date: 2026-03-31"],
            ["Currency: USD", "Amounts In: Millions"],
            ["Particulars", "Note No", "2026-03-31", "2025-03-31"],
            ["Current Assets", "", "", ""],
            ["Cash and Cash Equivalents", 1, 500, 450],
            ["Trade Receivables", 2, 300, 280],
            ["Non-Current Assets", "", "", ""],
            ["Property Plant and Equipment", 3, 1200, 1100],
            ["Total Assets", "", 2000, 1830],
            ["Current Liabilities", "", "", ""],
            ["Accounts Payable", 4, 400, 350],
            ["Non-Current Liabilities", "", "", ""],
            ["Long-term Debt", 5, 600, 580],
            ["Total Liabilities", "", 1000, 930],
            ["Equity", "", "", ""],
            ["Common Stock", "", 800, 800],
            ["Retained Earnings", "", 200, 100],
            ["Total Equity", "", 1000, 900],
        ]
        content = create_test_xlsx({"Financial Position": rows})
        bs = parse_balance_sheet(content, file_kind="xlsx", document_id=TEST_DOC_ID)

        assert bs.company == "Global Synthetic Corp"
        assert bs.reporting_date == date(2026, 3, 31)
        assert bs.currency == "USD"
        assert bs.unit_scale == 1000000

        # Current period
        assert bs.assets.current[0].value == Decimal("500")
        assert bs.assets.total == Decimal("2000")
        assert bs.source_metadata.sheet_name == "Financial Position"

        # Prior period in unmapped
        prior_items = [u for u in bs.unmapped if u.reason == "prior_period_value"]
        assert len(prior_items) == 10
        prior_cash = next(
            u for u in prior_items if u.raw_label == "Cash and Cash Equivalents"
        )
        assert prior_cash.raw_value == "2025-03-31: 450"

    def test_layout_b_reversed_period_columns_xlsx(self) -> None:
        """Verifies column order independence in Layout B XLSX."""
        rows = [
            ["Reporting Date: 2026-03-31"],
            ["Particulars", "Note No", "2025-03-31", "2026-03-31"],
            ["Current Assets", "", "", ""],
            ["Cash", 1, 450, 500],
            ["Total Assets", "", 1830, 2000],
        ]
        content = create_test_xlsx({"Reversed Sheet": rows})
        bs = parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)

        assert bs.assets.current[0].value == Decimal("500")
        assert bs.assets.total == Decimal("2000")
        prior_cash = next(u for u in bs.unmapped if u.reason == "prior_period_value")
        assert prior_cash.raw_value == "2025-03-31: 450"

    def test_native_excel_dates_and_floats(self) -> None:
        """Tests native Excel date cells and float cells converted via shortest string Decimal."""
        rows = [
            ["Company: Date Test"],
            ["Reporting Date", datetime(2026, 3, 31, 0, 0)],
            ["Particulars", "Amount"],
            ["Current Assets", ""],
            ["Cash", 1234.56],
            ["Total Assets", 1234.56],
        ]
        content = create_test_xlsx({"Sheet1": rows})
        bs = parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)

        assert bs.reporting_date == date(2026, 3, 31)
        assert bs.assets.current[0].value == Decimal("1234.56")
        assert isinstance(bs.assets.current[0].value, Decimal)

    def test_worksheet_selection_with_cover_sheet(self) -> None:
        """Scans multiple sheets, ignores non-table cover sheet, and selects the matching sheet."""
        cover_rows = [
            ["FinGenie Financial Export"],
            ["Prepared by: Accounting Department"],
            ["Notice: For internal review only"],
        ]
        bs_rows = [
            ["Reporting Date: 2026-01-31"],
            ["Particulars", "Amount"],
            ["Current Assets", ""],
            ["Cash", 500],
            ["Total Assets", 500],
        ]
        content = create_test_xlsx(
            {"Cover": cover_rows, "Audited Balance Sheet": bs_rows}
        )
        bs = parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)

        assert bs.source_metadata.sheet_name == "Audited Balance Sheet"
        assert bs.assets.total == Decimal("500")


class TestBalanceSheetXLSXErrorsAndSecurity:
    """Verifies security bounds, formula rejection, boolean rejection, and sheet selection errors."""

    def test_ambiguous_multiple_matching_worksheets_rejected(self) -> None:
        """Workbooks with multiple candidate balance sheet sheets raise AmbiguousWorksheetError."""
        bs_rows = [
            ["Reporting Date: 2026-01-31"],
            ["Particulars", "Amount"],
            ["Cash", 100],
        ]
        content = create_test_xlsx({"SheetA": bs_rows, "SheetB": bs_rows})
        with pytest.raises(AmbiguousWorksheetError, match="multiple worksheets"):
            parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)

    def test_no_matching_worksheet_raises_unsupported_format(self) -> None:
        """Workbooks with zero matching sheets raise UnsupportedFormatError."""
        random_rows = [["Hello", "World"], ["Foo", "Bar"]]
        content = create_test_xlsx({"Random": random_rows})
        with pytest.raises(UnsupportedFormatError, match="No worksheet matches"):
            parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)

    def test_boolean_amount_strictly_rejected(self) -> None:
        """Boolean cells in amount columns raise InvalidStatementError."""
        rows = [
            ["Reporting Date: 2026-01-31"],
            ["Particulars", "Amount"],
            ["Current Assets", ""],
            ["Cash", True],
        ]
        content = create_test_xlsx({"Sheet1": rows})
        with pytest.raises(InvalidStatementError, match="Boolean value is not allowed"):
            parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)

    def test_formula_in_financial_cell_rejected(self) -> None:
        """Formulas in financial cells are strictly rejected."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Formulas"
        ws.append(["Reporting Date: 2026-01-31"])
        ws.append(["Particulars", "Amount"])
        ws.append(["Cash", 100])
        # OpenPyXL cell with formula
        cell = ws.cell(row=4, column=2, value="=B3*2")
        cell.data_type = "f"

        stream = io.BytesIO()
        wb.save(stream)
        content = stream.getvalue()

        with pytest.raises(InvalidStatementError, match="Formula found"):
            parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)

    def test_macro_enabled_xlsm_rejected(self) -> None:
        """Macro-enabled workbooks containing vbaProject.bin raise UnsupportedFormatError."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", b"<Types/>")
            zf.writestr("xl/workbook.xml", b"<workbook/>")
            zf.writestr("xl/vbaProject.bin", b"fake macro binary")
        with pytest.raises(UnsupportedFormatError, match="Macro-enabled workbooks"):
            parse_balance_sheet_xlsx(buf.getvalue(), document_id=TEST_DOC_ID)

    def test_zip_bomb_decompression_guard(self) -> None:
        """Workbooks with expanded uncompressed size > 25 MiB raise ResourceLimitError."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", b"<Types/>")
            zf.writestr("xl/workbook.xml", b"<workbook/>")
            # 26 MiB uncompressed zeros
            zf.writestr("xl/worksheets/sheet1.xml", b"\x00" * (26 * 1024 * 1024))
        with pytest.raises(ResourceLimitError, match="Expanded XLSX content"):
            parse_balance_sheet_xlsx(buf.getvalue(), document_id=TEST_DOC_ID)

    def test_sparse_coordinate_bounds_guard(self) -> None:
        """Worksheets with extreme coordinates (>20,000 rows or >50 columns) raise ResourceLimitError."""
        sheet_xml = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            b'<dimension ref="A1:Z25000"/>'
            b'<sheetData><row r="25000"><c r="A25000"/></row></sheetData>'
            b"</worksheet>"
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", b"<Types/>")
            zf.writestr("xl/workbook.xml", b"<workbook/>")
            zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)

        with pytest.raises(ResourceLimitError, match="Worksheet coordinates exceed"):
            parse_balance_sheet_xlsx(buf.getvalue(), document_id=TEST_DOC_ID)


class TestBalanceSheetXLSXParityPolicies:
    """Verifies that XLSX parser has 100% parity with CSV parser policies."""

    def test_conflicting_currency_declarations_rejected(self) -> None:
        """Conflicting currency declarations in XLSX raise InvalidStatementError."""
        rows = [
            ["Reporting Date: 2026-03-31"],
            ["Currency: INR", "Currency: USD"],
            ["Particulars", "Amount"],
            ["Current Assets", ""],
            ["Cash", 100],
        ]
        content = create_test_xlsx({"Sheet1": rows})
        with pytest.raises(
            InvalidStatementError,
            match="Contradictory currency declarations",
        ):
            parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)

    def test_repeated_identical_metadata_preserves_first_seen_row(self) -> None:
        """Repeated identical metadata declarations preserve the first-seen row in source_locations."""
        rows = [
            ["Reporting Date: 2026-03-31"],
            ["Currency: INR"],
            ["Currency: INR"],
            ["Particulars", "Amount"],
            ["Current Assets", ""],
            ["Cash", 100],
        ]
        content = create_test_xlsx({"Sheet1": rows})
        bs = parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)
        assert bs.currency == "INR"
        assert bs.source_locations["currency"].source_row == 2

    def test_ambiguous_currency_declaration_routes_to_unmapped(self) -> None:
        """Ambiguous currency symbol e.g. 'RS.' routes to unmapped with reason ambiguous_currency."""
        rows = [
            ["Reporting Date: 2026-03-31"],
            ["Currency: RS."],
            ["Particulars", "Amount"],
            ["Current Assets", ""],
            ["Cash", 100],
        ]
        content = create_test_xlsx({"Sheet1": rows})
        bs = parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)
        assert bs.currency is None
        ambig = [u for u in bs.unmapped if u.reason == "ambiguous_currency"]
        assert len(ambig) == 1
        assert ambig[0].raw_value == "RS."

    def test_conflicting_duplicate_scalar_totals_rejected(self) -> None:
        """Conflicting total assets declarations in XLSX raise InvalidStatementError."""
        rows = [
            ["Reporting Date: 2026-03-31"],
            ["Particulars", "Amount"],
            ["Current Assets", ""],
            ["Cash", 100],
            ["Total Assets", 100],
            ["Total Assets", 200],
        ]
        content = create_test_xlsx({"Sheet1": rows})
        with pytest.raises(
            InvalidStatementError,
            match="Conflicting value for duplicate scalar field 'assets.total'",
        ):
            parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)

    def test_duplicate_scalar_present_vs_blank_rejected(self) -> None:
        """Reported total followed by a blank total in XLSX raises InvalidStatementError."""
        rows = [
            ["Reporting Date: 2026-03-31"],
            ["Particulars", "Amount"],
            ["Current Assets", ""],
            ["Cash", 100],
            ["Total Assets", 100],
            ["Total Assets", ""],
        ]
        content = create_test_xlsx({"Sheet1": rows})
        with pytest.raises(
            InvalidStatementError,
            match="Conflicting value for duplicate scalar field 'assets.total'",
        ):
            parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)

    def test_identical_duplicate_total_accepted_with_repeated_reported_value(
        self,
    ) -> None:
        """Identical duplicate total is accepted, preserving duplicate row in unmapped with repeated_reported_value."""
        rows = [
            ["Reporting Date: 2026-03-31"],
            ["Particulars", "Amount"],
            ["Current Assets", ""],
            ["Cash", 100],
            ["Total Assets", 100],
            ["Total Assets", 100],
        ]
        content = create_test_xlsx({"Sheet1": rows})
        bs = parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)
        assert bs.assets.total == Decimal("100")
        assert bs.source_locations["assets.total"].source_row == 5
        repeated = [u for u in bs.unmapped if u.reason == "repeated_reported_value"]
        assert len(repeated) == 1
        assert repeated[0].source_row == 6
        assert repeated[0].raw_label == "Total Assets"
        assert repeated[0].raw_value == "100"

    def test_tracked_empty_padding_columns_accepted(self) -> None:
        """XLSX table with empty padding columns parses correctly at actual indices."""
        rows = [
            ["Reporting Date: 2026-03-31"],
            ["", "Particulars", "", "Amount", ""],
            ["", "Current Assets", "", "", ""],
            ["", "Cash", "", 100, ""],
            ["", "Total Assets", "", 100, ""],
        ]
        content = create_test_xlsx({"Sheet1": rows})
        bs = parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)
        assert len(bs.assets.current) == 1
        assert bs.assets.current[0].canonical_field == "cash"
        assert bs.assets.current[0].value == Decimal("100")
        assert bs.assets.total == Decimal("100")

    def test_extra_populated_column_in_data_row_rejected(self) -> None:
        """Populated cell in an unassigned column raises InvalidStatementError in XLSX."""
        rows = [
            ["Reporting Date: 2026-03-31"],
            ["Particulars", "Amount"],
            ["Current Assets", ""],
            ["Cash", 100, "ExtraValue"],
        ]
        content = create_test_xlsx({"Sheet1": rows})
        with pytest.raises(
            InvalidStatementError,
            match="Unexpected populated cell in unassigned column",
        ):
            parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)

    def test_blank_amounts_preserved_with_source_locations(self) -> None:
        """Blank amounts on Cash and Total Assets in XLSX preserve LineItem(value=None) and source_locations."""
        rows = [
            ["Reporting Date: 2026-03-31"],
            ["Particulars", "Amount"],
            ["Current Assets", ""],
            ["Cash", ""],
            ["Total Assets", ""],
            ["Equity", ""],
            ["Retained Earnings", ""],
            ["Total Equity", ""],
        ]
        content = create_test_xlsx({"Sheet1": rows})
        bs = parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)
        assert len(bs.assets.current) == 1
        assert bs.assets.current[0].canonical_field == "cash"
        assert bs.assets.current[0].value is None
        assert bs.assets.current[0].source_row == 4

        assert bs.assets.total is None
        assert bs.source_locations["assets.total"].source_row == 5

        assert bs.equity.retained_earnings is None
        assert bs.source_locations["equity.retained_earnings"].source_row == 7

        assert bs.equity.total is None
        assert bs.source_locations["equity.total"].source_row == 8

    def test_root_transition_resets_subsection_state(self) -> None:
        """Root transition from Assets to Liabilities in XLSX resets subsection; rows without subsection go to ambiguous_section."""
        rows = [
            ["Reporting Date: 2026-03-31"],
            ["Particulars", "Amount"],
            ["Non-Current Assets", ""],
            ["Equipment", 100],
            ["Liabilities", ""],
            ["Trade Payables", 20],
            ["Total Liabilities", 20],
        ]
        content = create_test_xlsx({"Sheet1": rows})
        bs = parse_balance_sheet_xlsx(content, document_id=TEST_DOC_ID)
        assert len(bs.assets.non_current) == 1
        assert bs.assets.non_current[0].canonical_field == "property_plant_equipment"
        assert bs.assets.non_current[0].value == Decimal("100")

        # Trade Payables was under root Liabilities with no subsection -> unmapped ambiguous_section
        assert len(bs.liabilities.current) == 0
        assert len(bs.liabilities.non_current) == 0
        ambig = [u for u in bs.unmapped if u.reason == "ambiguous_section"]
        assert len(ambig) == 1
        assert ambig[0].raw_label == "Trade Payables"
        assert ambig[0].raw_value == "20"
        assert ambig[0].source_row == 6

        # Total Liabilities is a recognized total scalar and is preserved
        assert bs.liabilities.total == Decimal("20")
        assert bs.source_locations["liabilities.total"].source_row == 7
