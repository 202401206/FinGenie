"""Cross-component integration tests verifying parser output compatibility with persistence boundaries."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from app.parsers.bank_statement import parse_bank_statement
from app.schemas.bank_statement import BankStatement

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DOC_ID = UUID("30000000-0000-4000-8000-000000000003")


class TestPersistenceCompatibility:
    """Verifies that parsed statement models cleanly serialize and satisfy DB repository constraints."""

    def test_csv_end_to_end_persistence_trace(self) -> None:
        """Traces a CSV statement through parsing and ensures exact types for DB persistence."""
        csv_path = FIXTURES_DIR / "synthetic_bank_statement.csv"
        content = csv_path.read_bytes()

        statement = parse_bank_statement(content, file_kind="csv", document_id=DOC_ID)

        # 1. Verify caller document_id survives
        assert statement.source_metadata.document_id == DOC_ID

        # 2. Verify CSV sheet_name is None
        assert statement.source_metadata.sheet_name is None

        # 3. Model dump in python mode for repository handoff
        db_payload = statement.model_dump(mode="python")

        # Decimal amounts must survive as native Decimal (not float or string)
        assert isinstance(db_payload["opening_balance"], Decimal)
        assert isinstance(db_payload["closing_balance"], Decimal)

        for tx in db_payload["transactions"]:
            assert isinstance(tx["date"], date)
            assert isinstance(tx["debit"], Decimal)
            assert isinstance(tx["credit"], Decimal)
            assert isinstance(tx["balance"], Decimal)
            assert isinstance(tx["source_row"], int)
            assert tx["source_row"] > 0

        # Try validating against app.db.models.TransactionRecord if present on branch
        try:
            from app.db.models import TransactionRecord

            for idx, tx in enumerate(db_payload["transactions"], start=1):
                tx_record_dict = dict(tx)
                tx_record_dict["id"] = UUID(f"00000000-0000-4000-8000-{idx:012d}")
                tx_record_dict["document_id"] = DOC_ID
                record = TransactionRecord.model_validate(tx_record_dict)
                assert record.debit == tx["debit"]
                assert record.credit == tx["credit"]
                assert record.balance == tx["balance"]
                assert record.source_row == tx["source_row"]
        except ImportError:
            pass  # app.db.models may be on an unmerged persistence branch

    def test_xlsx_end_to_end_persistence_trace(self) -> None:
        """Traces an XLSX statement through parsing and ensures exact sheet name and Decimal types."""
        from tests.parsers.test_bank_xlsx_parser import _create_synthetic_xlsx

        xlsx_bytes = _create_synthetic_xlsx(sheet_name="Checking_2026")
        statement = parse_bank_statement(
            xlsx_bytes, file_kind="xlsx", document_id=DOC_ID
        )

        assert statement.source_metadata.document_id == DOC_ID
        assert statement.source_metadata.sheet_name == "Checking_2026"

        db_payload = statement.model_dump(mode="python")
        assert isinstance(db_payload["transactions"][0]["credit"], Decimal)
        assert db_payload["transactions"][0]["credit"] == Decimal("5000")

    def test_json_roundtrip_wire_compatibility(self) -> None:
        """Verifies that model_dump(mode='json') produces valid JSON adhering to wire contract."""
        csv_path = FIXTURES_DIR / "synthetic_bank_statement.csv"
        content = csv_path.read_bytes()

        statement = parse_bank_statement(content, file_kind="csv", document_id=DOC_ID)

        # JSON mode dump
        json_data = statement.model_dump(mode="json")
        serialized_str = json.dumps(json_data)
        assert len(serialized_str) > 0

        # Roundtrip back through Pydantic
        reconstructed = BankStatement.model_validate_json(serialized_str)
        assert reconstructed.bank == statement.bank
        assert reconstructed.opening_balance == statement.opening_balance
        assert len(reconstructed.transactions) == len(statement.transactions)
        assert reconstructed.transactions[0].credit == Decimal("5000")

    def test_unmapped_items_json_serializable(self) -> None:
        """All unmapped entries must be serializable without custom encoders."""
        csv_path = FIXTURES_DIR / "synthetic_bank_statement.csv"
        statement = parse_bank_statement(
            csv_path.read_bytes(), file_kind="csv", document_id=DOC_ID
        )

        assert len(statement.unmapped) > 0
        unmapped_data = [item.model_dump(mode="json") for item in statement.unmapped]
        json_str = json.dumps(unmapped_data)
        assert "Unrecognized export note" in json_str

    def test_extreme_decimal_precision_edge_cases(self) -> None:
        """Tests very large and fractional decimal amounts without precision loss."""
        csv_data = (
            "Date,Description,Debit,Credit,Balance\n"
            "2026-01-01,Large transfer,,1000000000.00,1000000000.00\n"
            "2026-01-02,Fractional fee,0.0001,,999999999.9999\n"
        ).encode("utf-8")

        statement = parse_bank_statement(csv_data, file_kind="csv", document_id=DOC_ID)
        t1, t2 = statement.transactions

        assert t1.credit == Decimal("1000000000.00")
        assert t2.debit == Decimal("0.0001")
        assert t2.balance == Decimal("999999999.9999")
