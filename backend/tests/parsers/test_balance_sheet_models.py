"""Unit tests for balance sheet Pydantic models, fixtures, and safe parser errors."""

import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import openpyxl
import pytest
from pydantic import ValidationError

from app.parsers.errors import (
    AmbiguousWorksheetError,
    BalanceSheetParserError,
    BankStatementParserError,
    InvalidStatementError,
    ResourceLimitError,
    StatementParserError,
    UnsupportedFormatError,
)
from app.schemas.balance_sheet import (
    BalanceSheet,
    Equity,
    LineItem,
    SectionItems,
    SourceLocation,
    SourceMetadata,
    UnmappedItem,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CONTRACTS_EXAMPLE = (
    Path(__file__).parents[3] / "contracts" / "examples" / "balance-sheet.json"
)


def create_in_memory_xlsx(
    rows: list[list[object]], sheet_name: str = "Balance Sheet"
) -> bytes:
    """Helper to generate an in-memory XLSX workbook for format testing."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    for row in rows:
        ws.append(row)
    stream = io.BytesIO()
    wb.save(stream)
    return stream.getvalue()


class TestBalanceSheetFixtures:
    """Verifies parsing of synthetic fixtures against the BalanceSheet model."""

    def test_valid_fixture_matches_contract_example(self) -> None:
        """Ensures the hand-authored contracts/examples/balance-sheet.json validates cleanly."""
        assert CONTRACTS_EXAMPLE.exists(), (
            f"Missing contract example at {CONTRACTS_EXAMPLE}"
        )
        with open(CONTRACTS_EXAMPLE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        bs = BalanceSheet.model_validate(raw_data)

        assert bs.company == "Synthetic Demo Company"
        assert bs.reporting_date == date(2026, 1, 31)
        assert bs.currency == "INR"
        assert bs.unit_scale == 100000

        # Assets validation
        assert len(bs.assets.current) == 2
        assert bs.assets.current[0].canonical_field == "cash"
        assert bs.assets.current[0].raw_label == "Cash"
        assert bs.assets.current[0].value == Decimal("100")
        assert bs.assets.current[0].source_row == 6

        assert bs.assets.current[1].canonical_field == "receivables"
        assert bs.assets.current[1].raw_label == "Receivables"
        assert bs.assets.current[1].value == Decimal("50")
        assert bs.assets.current[1].source_row == 7

        assert len(bs.assets.non_current) == 1
        assert bs.assets.non_current[0].canonical_field == "property_plant_equipment"
        assert bs.assets.non_current[0].raw_label == "Equipment"
        assert bs.assets.non_current[0].value == Decimal("150")
        assert bs.assets.non_current[0].source_row == 9

        assert bs.assets.total == Decimal("300")

        # Liabilities validation
        assert len(bs.liabilities.current) == 1
        assert bs.liabilities.current[0].canonical_field == "trade_payables"
        assert bs.liabilities.current[0].raw_label == "Payables"
        assert bs.liabilities.current[0].value == Decimal("80")
        assert bs.liabilities.current[0].source_row == 12

        assert len(bs.liabilities.non_current) == 1
        assert bs.liabilities.non_current[0].canonical_field == "long_term_borrowings"
        assert bs.liabilities.non_current[0].raw_label == "Long-term loan"
        assert bs.liabilities.non_current[0].value == Decimal("40")
        assert bs.liabilities.non_current[0].source_row == 15

        assert bs.liabilities.total == Decimal("120")

        # Equity validation
        assert bs.equity.share_capital == Decimal("150")
        assert bs.equity.retained_earnings == Decimal("30")
        assert bs.equity.total == Decimal("180")

        # Source metadata & locations
        assert bs.source_metadata.document_id == UUID(
            "10000000-0000-4000-8000-000000000002"
        )
        assert bs.source_metadata.sheet_name == "Balance Sheet"
        assert bs.source_locations["company"].source_row == 1
        assert bs.source_locations["reporting_date"].source_row == 2
        assert bs.source_locations["currency"].source_row == 3
        assert bs.source_locations["unit_scale"].source_row == 3
        assert bs.source_locations["assets.total"].source_row == 10
        assert bs.source_locations["liabilities.total"].source_row == 16
        assert bs.source_locations["equity.share_capital"].source_row == 18
        assert bs.source_locations["equity.retained_earnings"].source_row == 19
        assert bs.source_locations["equity.total"].source_row == 20

    def test_layout_a_fixture_from_fixtures_directory(self) -> None:
        """Validates the synthetic Layout A fixture stored in tests/parsers/fixtures/."""
        fixture_path = FIXTURES_DIR / "synthetic_balance_sheet_layout_a.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        bs = BalanceSheet.model_validate(raw_data)
        assert bs.company == "Synthetic Demo Company"
        assert bs.reporting_date == date(2026, 1, 31)
        assert bs.currency == "INR"
        assert bs.unit_scale == 100000
        assert bs.assets.total == Decimal("300")
        assert bs.liabilities.total == Decimal("120")
        assert bs.equity.total == Decimal("180")

    def test_layout_b_fixture_from_fixtures_directory(self) -> None:
        """Validates the synthetic Layout B fixture preserving prior period in unmapped."""
        fixture_path = FIXTURES_DIR / "synthetic_balance_sheet_layout_b.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        bs = BalanceSheet.model_validate(raw_data)
        assert bs.company == "Global Synthetic Corp"
        assert bs.reporting_date == date(2026, 3, 31)
        assert bs.currency == "USD"
        assert bs.unit_scale == 1000000

        # Current period assets
        assert bs.assets.current[0].value == Decimal("500")
        assert bs.assets.total == Decimal("2000")

        # Prior period values are preserved in unmapped
        assert len(bs.unmapped) == 10
        prior_cash = next(
            u for u in bs.unmapped if u.raw_label == "Cash and Cash Equivalents"
        )
        assert prior_cash.raw_value == "2025-03-31: 450"
        assert prior_cash.reason == "prior_period_value"
        assert prior_cash.source_row == 6

    def test_minimal_fixture_with_null_metadata(self) -> None:
        """Validates that all optional metadata can be null without validation errors."""
        fixture_path = FIXTURES_DIR / "balance_sheet_minimal.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        bs = BalanceSheet.model_validate(raw_data)
        assert bs.company is None
        assert bs.reporting_date == date(2026, 1, 31)
        assert bs.currency is None
        assert bs.unit_scale is None
        assert bs.assets.total is None
        assert bs.liabilities.total is None
        assert bs.equity.total is None
        assert bs.unmapped == []


class TestLineItemAndSectionModels:
    """Tests strict decimal handling, boolean rejection, and source row validation."""

    def test_decimal_precision_is_preserved(self) -> None:
        """Exact Decimal values must not be converted or rounded through binary float."""
        item = LineItem(
            canonical_field="cash",
            raw_label="Petty Cash",
            value=Decimal("1234567.890123"),
            source_row=10,
        )
        assert item.value == Decimal("1234567.890123")
        assert isinstance(item.value, Decimal)

    def test_real_zero_is_preserved(self) -> None:
        """A reported zero must remain Decimal('0') and not be converted to None."""
        item = LineItem(
            canonical_field="cash",
            raw_label="Zero Balance",
            value=Decimal("0"),
            source_row=5,
        )
        assert item.value == Decimal("0")
        assert item.value is not None

    def test_missing_amount_is_none(self) -> None:
        """Missing financial amount remains None without fabricating zero."""
        item = LineItem(
            canonical_field="other_current_assets",
            raw_label="Unspecified Asset",
            value=None,
            source_row=8,
        )
        assert item.value is None

    def test_negative_retained_earnings_allowed(self) -> None:
        """Negative equity values (accumulated losses/deficit) are valid."""
        equity = Equity(
            share_capital=Decimal("100000"),
            retained_earnings=Decimal("-25000"),
            total=Decimal("75000"),
        )
        assert equity.retained_earnings == Decimal("-25000")
        assert equity.total == Decimal("75000")

    def test_boolean_amounts_rejected(self) -> None:
        """Boolean values (True/False) must be strictly rejected for all monetary fields."""
        with pytest.raises(ValidationError):
            LineItem(
                canonical_field="cash",
                raw_label="Invalid boolean",
                value=True,  # type: ignore[arg-type]
                source_row=1,
            )

        with pytest.raises(ValidationError):
            SectionItems(
                current=[],
                non_current=[],
                total=False,  # type: ignore[arg-type]
            )

        with pytest.raises(ValidationError):
            Equity(
                share_capital=True,  # type: ignore[arg-type]
                retained_earnings=Decimal("0"),
                total=Decimal("0"),
            )

        with pytest.raises(ValidationError):
            Equity(
                share_capital=Decimal("100"),
                retained_earnings=False,  # type: ignore[arg-type]
                total=Decimal("100"),
            )

    def test_non_finite_amounts_rejected(self) -> None:
        """NaN and infinite amounts must be rejected."""
        for non_finite in (
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
        ):
            with pytest.raises(ValidationError):
                LineItem(
                    canonical_field="cash",
                    raw_label="Non-finite",
                    value=non_finite,
                    source_row=1,
                )

            with pytest.raises(ValidationError):
                SectionItems(current=[], non_current=[], total=non_finite)

            with pytest.raises(ValidationError):
                Equity(
                    share_capital=non_finite,
                    retained_earnings=Decimal("0"),
                    total=Decimal("0"),
                )

    def test_source_row_must_be_positive_integer(self) -> None:
        """Source rows are 1-based positive integers; zero, negative, and booleans fail."""
        with pytest.raises(ValidationError):
            LineItem(
                canonical_field="cash",
                raw_label="Zero row",
                value=Decimal("10"),
                source_row=0,
            )

        with pytest.raises(ValidationError):
            LineItem(
                canonical_field="cash",
                raw_label="Negative row",
                value=Decimal("10"),
                source_row=-3,
            )

        with pytest.raises(ValidationError):
            LineItem(
                canonical_field="cash",
                raw_label="Boolean row",
                value=Decimal("10"),
                source_row=True,  # type: ignore[arg-type]
            )


class TestMetadataAndScaleValidation:
    """Tests currency code validation, scale multipliers, and error handling."""

    def test_supported_currencies_inr_and_usd(self) -> None:
        """INR and USD are supported; whitespace and lowercase are normalized."""
        bs_inr = BalanceSheet(
            reporting_date=date(2026, 1, 31),
            currency="inr",
            assets=SectionItems(),
            liabilities=SectionItems(),
            equity=Equity(),
            source_metadata=SourceMetadata(
                document_id=UUID("00000000-0000-4000-8000-000000000001")
            ),
        )
        assert bs_inr.currency == "INR"

        bs_usd = BalanceSheet(
            reporting_date=date(2026, 1, 31),
            currency="  USD  ",
            assets=SectionItems(),
            liabilities=SectionItems(),
            equity=Equity(),
            source_metadata=SourceMetadata(
                document_id=UUID("00000000-0000-4000-8000-000000000001")
            ),
        )
        assert bs_usd.currency == "USD"

    def test_unsupported_currency_rejected(self) -> None:
        """Unsupported currencies (e.g. EUR, GBP) raise ValidationError."""
        for unsupported in ("EUR", "GBP", "JPY", "XYZ", "123"):
            with pytest.raises(ValidationError) as exc_info:
                BalanceSheet(
                    reporting_date=date(2026, 1, 31),
                    currency=unsupported,
                    assets=SectionItems(),
                    liabilities=SectionItems(),
                    equity=Equity(),
                    source_metadata=SourceMetadata(
                        document_id=UUID("00000000-0000-4000-8000-000000000001")
                    ),
                )
            assert "Unsupported balance sheet currency" in str(exc_info.value)

    def test_all_allowed_unit_scales(self) -> None:
        """All agreed scales (1, 1000, 100000, 1000000, 10000000) validate cleanly."""
        allowed_scales = [1, 1_000, 100_000, 1_000_000, 10_000_000]
        for scale in allowed_scales:
            bs = BalanceSheet(
                reporting_date=date(2026, 1, 31),
                unit_scale=scale,
                assets=SectionItems(),
                liabilities=SectionItems(),
                equity=Equity(),
                source_metadata=SourceMetadata(
                    document_id=UUID("00000000-0000-4000-8000-000000000001")
                ),
            )
            assert bs.unit_scale == scale

    def test_invalid_and_boolean_unit_scales_rejected(self) -> None:
        """Unrecognized, float, or boolean scales are rejected."""
        for invalid_scale in (True, False, 500, 10000, 1.0, "1000"):
            with pytest.raises(ValidationError):
                BalanceSheet(
                    reporting_date=date(2026, 1, 31),
                    unit_scale=invalid_scale,  # type: ignore[arg-type]
                    assets=SectionItems(),
                    liabilities=SectionItems(),
                    equity=Equity(),
                    source_metadata=SourceMetadata(
                        document_id=UUID("00000000-0000-4000-8000-000000000001")
                    ),
                )

    def test_unmapped_item_structure(self) -> None:
        """Unmapped preserves location, label, value, and standard reason."""
        item = UnmappedItem(
            source_row=15,
            raw_label="Contingent Liabilities",
            raw_value="50000",
            reason="unrecognized_note",
        )
        assert item.source_row == 15
        assert item.raw_label == "Contingent Liabilities"
        assert item.raw_value == "50000"
        assert item.reason == "unrecognized_note"

    def test_source_location_structure(self) -> None:
        """SourceLocation encapsulates 1-based source row reference."""
        loc = SourceLocation(source_row=5)
        assert loc.source_row == 5
        with pytest.raises(ValidationError):
            SourceLocation(source_row=0)
        with pytest.raises(ValidationError):
            SourceLocation(source_row=True)  # type: ignore[arg-type]


class TestParserErrorsHierarchy:
    """Verifies that all parser exceptions inherit from StatementParserError."""

    def test_parser_errors_hierarchy(self) -> None:
        """All parser exceptions inherit from StatementParserError, BankStatementParserError, and BalanceSheetParserError."""
        errors = [
            UnsupportedFormatError("Unsupported balance sheet format .pdf"),
            InvalidStatementError("Missing reporting date column in Layout B"),
            AmbiguousWorksheetError("Multiple sheets match balance sheet layout"),
            ResourceLimitError("Workbook exceeds 50 columns bound"),
        ]
        for err in errors:
            assert isinstance(err, StatementParserError)
            assert isinstance(err, BankStatementParserError)
            assert isinstance(err, BalanceSheetParserError)
            assert isinstance(err, Exception)
            assert len(err.message) > 0


class TestPersistenceBoundaryCompatibility:
    """Verifies that model_dump(mode='python') cleanly satisfies the persistence boundary."""

    def test_model_dump_python_preserves_decimals_and_dates(self) -> None:
        """Ensures mode='python' produces Decimals, dates, and UUIDs for DB persistence."""
        bs = BalanceSheet(
            company="Persistence Demo",
            reporting_date=date(2026, 1, 31),
            currency="INR",
            unit_scale=100000,
            assets=SectionItems(
                current=[
                    LineItem(
                        canonical_field="cash",
                        raw_label="Cash",
                        value=Decimal("100"),
                        source_row=6,
                    )
                ],
                total=Decimal("100"),
            ),
            liabilities=SectionItems(
                current=[
                    LineItem(
                        canonical_field="trade_payables",
                        raw_label="Payables",
                        value=Decimal("40"),
                        source_row=10,
                    )
                ],
                total=Decimal("40"),
            ),
            equity=Equity(
                share_capital=Decimal("50"),
                retained_earnings=Decimal("10"),
                total=Decimal("60"),
            ),
            source_metadata=SourceMetadata(
                document_id=UUID("12345678-1234-5678-1234-567812345678"),
                sheet_name="Balance Sheet",
            ),
            source_locations={
                "reporting_date": SourceLocation(source_row=2),
                "assets.total": SourceLocation(source_row=7),
            },
        )
        dumped = bs.model_dump(mode="python")

        assert isinstance(dumped["reporting_date"], date)
        assert isinstance(dumped["assets"]["total"], Decimal)
        assert isinstance(dumped["assets"]["current"][0]["value"], Decimal)
        assert isinstance(dumped["equity"]["retained_earnings"], Decimal)
        assert isinstance(dumped["source_metadata"]["document_id"], UUID)

    def test_compatibility_with_parsed_read_model(self) -> None:
        """Verifies that model_dump cleanly validates against ParsedBalanceSheet in app/db/parsed_read_models.py."""
        from app.db.parsed_read_models import ParsedBalanceSheet

        with open(
            FIXTURES_DIR / "synthetic_balance_sheet_layout_a.json",
            "r",
            encoding="utf-8",
        ) as f:
            raw_data = json.load(f)

        bs = BalanceSheet.model_validate(raw_data)
        python_dump = bs.model_dump(mode="python")

        # Must cleanly pass the DB read model validator
        read_model = ParsedBalanceSheet.model_validate(python_dump)
        assert read_model.company == "Synthetic Demo Company"
        assert read_model.reporting_date == date(2026, 1, 31)
        assert read_model.currency == "INR"
        assert read_model.unit_scale == 100000
        assert read_model.assets.total == Decimal("300")


class TestInMemoryXlsxGeneration:
    """Verifies that synthetic data can be encoded into an XLSX workbook in memory."""

    def test_in_memory_xlsx_workbook_creation(self) -> None:
        """Generates an in-memory XLSX workbook matching Layout A structure."""
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
        ]
        xlsx_bytes = create_in_memory_xlsx(rows, sheet_name="Balance Sheet")
        assert len(xlsx_bytes) > 0
        assert xlsx_bytes.startswith(b"PK\x03\x04")

        # Load back with openpyxl to verify cell contents
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
        assert "Balance Sheet" in wb.sheetnames
        ws = wb["Balance Sheet"]
        assert ws.cell(row=1, column=1).value == "Company: Synthetic Demo Company"
        assert ws.cell(row=4, column=1).value == "Particulars"
        assert ws.cell(row=4, column=2).value == "Amount"
        assert ws.cell(row=6, column=2).value == 100
