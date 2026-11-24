"""Cross-component integration tests verifying balance sheet parser output compatibility with persistence boundaries."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from app.db.parsed_read_models import ParsedBalanceSheet
from app.parsers.balance_sheet import parse_balance_sheet
from app.schemas.balance_sheet import BalanceSheet
from tests.parsers.test_balance_sheet_xlsx_parser import create_test_xlsx

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DOC_ID = UUID("40000000-0000-4000-8000-000000000004")


class TestBalanceSheetPersistenceCompatibility:
    """Verifies that parsed balance sheet models cleanly satisfy DB read/save boundaries and JSON roundtrips."""

    def test_layout_a_csv_persistence_trace(self) -> None:
        """Traces Layout A CSV statement through parsing and validates against ParsedBalanceSheet."""
        csv_path = FIXTURES_DIR / "synthetic_balance_sheet_layout_a.csv"
        content = csv_path.read_bytes()

        bs = parse_balance_sheet(content, file_kind="csv", document_id=DOC_ID)

        # 1. Verify caller document_id survives
        assert bs.source_metadata.document_id == DOC_ID
        assert bs.source_metadata.sheet_name is None

        # 2. Model dump in python mode for repository handoff
        db_payload = bs.model_dump(mode="python")

        # Decimal amounts must survive as native Decimal (not float or string)
        assert isinstance(db_payload["assets"]["total"], Decimal)
        assert isinstance(db_payload["liabilities"]["total"], Decimal)
        assert isinstance(db_payload["equity"]["total"], Decimal)
        assert isinstance(db_payload["reporting_date"], date)
        assert isinstance(db_payload["source_metadata"]["document_id"], UUID)

        for item in db_payload["assets"]["current"]:
            assert isinstance(item["value"], Decimal)
            assert isinstance(item["source_row"], int)
            assert item["source_row"] > 0

        # 3. Validate cleanly against app.db.parsed_read_models.ParsedBalanceSheet
        read_model = ParsedBalanceSheet.model_validate(db_payload)
        assert read_model.company == "Synthetic Demo Company"
        assert read_model.reporting_date == date(2026, 1, 31)
        assert read_model.currency == "INR"
        assert read_model.unit_scale == 100000
        assert read_model.assets.total == Decimal("300")
        assert read_model.liabilities.total == Decimal("120")
        assert read_model.equity.total == Decimal("180")

    def test_layout_b_csv_persistence_trace(self) -> None:
        """Traces Layout B comparative CSV statement through parsing and validates against ParsedBalanceSheet."""
        csv_path = FIXTURES_DIR / "synthetic_balance_sheet_layout_b.csv"
        content = csv_path.read_bytes()

        bs = parse_balance_sheet(content, file_kind="csv", document_id=DOC_ID)

        assert bs.source_metadata.document_id == DOC_ID
        assert bs.source_metadata.sheet_name is None

        db_payload = bs.model_dump(mode="python")

        # Verify prior period values preserved in unmapped
        assert len(db_payload["unmapped"]) == 10
        for u in db_payload["unmapped"]:
            assert u["reason"] == "prior_period_value"
            assert "2025-03-31:" in u["raw_value"]
            assert u["source_row"] > 0

        # Validate against ParsedBalanceSheet
        read_model = ParsedBalanceSheet.model_validate(db_payload)
        assert read_model.company == "Global Synthetic Corp"
        assert read_model.reporting_date == date(2026, 3, 31)
        assert read_model.currency == "USD"
        assert read_model.unit_scale == 1000000
        assert read_model.assets.total == Decimal("2000")
        assert read_model.liabilities.total == Decimal("1000")
        assert read_model.equity.total == Decimal("1000")

    def test_layout_a_xlsx_persistence_trace(self) -> None:
        """Traces Layout A XLSX spreadsheet through parsing, verifying sheet_name and DB read model."""
        rows = [
            ["Company: Synthetic Demo Company"],
            ["Reporting Date: 2026-01-31"],
            ["Currency: INR", "Scale: Lakhs"],
            ["Particulars", "Amount"],
            ["Current Assets", ""],
            ["Cash", 100],
            ["Receivables", 50],
            ["Total Assets", 150],
            ["Current Liabilities", ""],
            ["Payables", 50],
            ["Total Liabilities", 50],
            ["Equity", ""],
            ["Share Capital", 80],
            ["Retained Earnings", 20],
            ["Total Equity", 100],
        ]
        xlsx_bytes = create_test_xlsx({"Audited Balance": rows})

        bs = parse_balance_sheet(xlsx_bytes, file_kind="xlsx", document_id=DOC_ID)

        assert bs.source_metadata.document_id == DOC_ID
        assert bs.source_metadata.sheet_name == "Audited Balance"

        db_payload = bs.model_dump(mode="python")
        read_model = ParsedBalanceSheet.model_validate(db_payload)
        assert read_model.source_metadata.sheet_name == "Audited Balance"
        assert read_model.assets.total == Decimal("150")

    def test_layout_b_xlsx_persistence_trace(self) -> None:
        """Traces Layout B XLSX comparative spreadsheet through parsing and validates DB read model."""
        rows = [
            ["Company: Global Synthetic Corp"],
            ["Reporting Date: 2026-03-31"],
            ["Currency: USD", "Amounts In: Millions"],
            ["Particulars", "Note No", "2026-03-31", "2025-03-31"],
            ["Current Assets", "", "", ""],
            ["Cash", 1, 500, 450],
            ["Total Assets", "", 500, 450],
            ["Current Liabilities", "", "", ""],
            ["Payables", 2, 200, 150],
            ["Total Liabilities", "", 200, 150],
            ["Equity", "", "", ""],
            ["Common Stock", "", 250, 250],
            ["Retained Earnings", "", 50, 50],
            ["Total Equity", "", 300, 300],
        ]
        xlsx_bytes = create_test_xlsx({"Comparative_FY26": rows})

        bs = parse_balance_sheet(xlsx_bytes, file_kind="xlsx", document_id=DOC_ID)

        assert bs.source_metadata.document_id == DOC_ID
        assert bs.source_metadata.sheet_name == "Comparative_FY26"

        db_payload = bs.model_dump(mode="python")
        read_model = ParsedBalanceSheet.model_validate(db_payload)
        assert read_model.source_metadata.sheet_name == "Comparative_FY26"
        assert read_model.assets.total == Decimal("500")

    def test_json_roundtrip_wire_compatibility(self) -> None:
        """Verifies that model_dump(mode='json') produces valid JSON adhering to wire contract."""
        csv_path = FIXTURES_DIR / "synthetic_balance_sheet_layout_a.csv"
        content = csv_path.read_bytes()

        bs = parse_balance_sheet(content, file_kind="csv", document_id=DOC_ID)

        # JSON mode dump
        json_data = bs.model_dump(mode="json")
        serialized_str = json.dumps(json_data)
        assert len(serialized_str) > 0

        # Roundtrip back through Pydantic
        reconstructed = BalanceSheet.model_validate_json(serialized_str)
        assert reconstructed.company == bs.company
        assert reconstructed.reporting_date == bs.reporting_date
        assert reconstructed.assets.total == bs.assets.total
        assert reconstructed.assets.current[0].value == Decimal("100")
        assert reconstructed.source_metadata.document_id == DOC_ID

    def test_null_metadata_persisted_cleanly(self) -> None:
        """Minimal balance sheet with null metadata survives dump and persistence boundary."""
        csv_text = """Reporting Date: 2026-01-31
Particulars,Amount
Current Assets,
Cash,100
"""
        bs = parse_balance_sheet(
            csv_text.encode("utf-8"), file_kind="csv", document_id=DOC_ID
        )
        db_payload = bs.model_dump(mode="python")

        read_model = ParsedBalanceSheet.model_validate(db_payload)
        assert read_model.company is None
        assert read_model.currency is None
        assert read_model.unit_scale is None
        assert read_model.assets.total is None
        assert read_model.liabilities.total is None
        assert read_model.equity.total is None

    def test_negative_retained_earnings_persisted_cleanly(self) -> None:
        """Negative equity values (accumulated losses) survive persistence validation."""
        csv_text = """Reporting Date: 2026-01-31
Particulars,Amount
Equity,
Share Capital,100
Retained Earnings,(30)
Total Equity,70
"""
        bs = parse_balance_sheet(
            csv_text.encode("utf-8"), file_kind="csv", document_id=DOC_ID
        )
        db_payload = bs.model_dump(mode="python")

        read_model = ParsedBalanceSheet.model_validate(db_payload)
        assert read_model.equity.share_capital == Decimal("100")
        assert read_model.equity.retained_earnings == Decimal("-30")
        assert read_model.equity.total == Decimal("70")
