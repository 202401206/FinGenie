"""Unit tests for bank statement Pydantic models, fixtures, and safe parser errors."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.parsers.errors import (
    AmbiguousWorksheetError,
    BankStatementParserError,
    InvalidStatementError,
    ResourceLimitError,
    UnsupportedFormatError,
)
from app.schemas.bank_statement import (
    BankStatement,
    BankTransaction,
    SourceLocation,
    SourceMetadata,
    Transaction,
    UnmappedItem,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CONTRACTS_EXAMPLE = (
    Path(__file__).parents[3] / "contracts" / "examples" / "bank-statement.json"
)


class TestBankStatementFixtures:
    """Verifies parsing of synthetic fixtures against the BankStatement model."""

    def test_valid_fixture_matches_contract_example(self) -> None:
        """Ensures the hand-authored contracts/examples/bank-statement.json validates cleanly."""
        assert CONTRACTS_EXAMPLE.exists(), (
            f"Missing contract example at {CONTRACTS_EXAMPLE}"
        )
        with open(CONTRACTS_EXAMPLE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        statement = BankStatement.model_validate(raw_data)

        assert statement.bank == "Synthetic Demo Bank"
        assert statement.account_holder == "Synthetic Person"
        assert statement.account_type == "savings"
        assert statement.currency == "INR"
        assert statement.period_start == date(2026, 1, 1)
        assert statement.period_end == date(2026, 1, 31)
        assert statement.opening_balance == Decimal("10000")
        assert statement.closing_balance == Decimal("12500")
        assert len(statement.transactions) == 3
        assert len(statement.unmapped) == 1
        assert statement.source_metadata.document_id == UUID(
            "10000000-0000-4000-8000-000000000001"
        )
        assert statement.source_metadata.sheet_name is None
        assert "opening_balance" in statement.source_locations
        assert statement.source_locations["opening_balance"].source_row == 4

    def test_valid_fixture_from_fixtures_directory(self) -> None:
        """Validates the synthetic fixture stored in tests/parsers/fixtures/."""
        fixture_path = FIXTURES_DIR / "bank_statement_valid.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        statement = BankStatement.model_validate(raw_data)
        assert len(statement.transactions) == 3
        first_tx = statement.transactions[0]
        assert first_tx.date == date(2026, 1, 5)
        assert first_tx.description == "Synthetic salary"
        assert first_tx.debit == Decimal("0")
        assert first_tx.credit == Decimal("5000")
        assert first_tx.balance == Decimal("15000")
        assert first_tx.source_row == 6

    def test_minimal_fixture_with_null_metadata(self) -> None:
        """Validates that all optional metadata can be null/None without validation errors."""
        fixture_path = FIXTURES_DIR / "bank_statement_minimal.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        statement = BankStatement.model_validate(raw_data)
        assert statement.bank is None
        assert statement.account_holder is None
        assert statement.account_type is None
        assert statement.currency is None
        assert statement.period_start is None
        assert statement.period_end is None
        assert statement.opening_balance is None
        assert statement.closing_balance is None
        assert len(statement.transactions) == 1
        assert statement.unmapped == []
        assert statement.source_locations == {}

    def test_invalid_period_dates_fixture(self) -> None:
        """Ensures that period_start > period_end is rejected."""
        fixture_path = FIXTURES_DIR / "bank_statement_invalid_dates.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        with pytest.raises(ValidationError) as exc_info:
            BankStatement.model_validate(raw_data)
        assert "period_start" in str(exc_info.value)
        assert "cannot be after period_end" in str(exc_info.value)


class TestBankTransactionModel:
    """Verifies strict field rules, decimal handling, and source row validation on BankTransaction."""

    def test_transaction_alias_is_identical(self) -> None:
        """Transaction is exported as an alias for BankTransaction."""
        assert Transaction is BankTransaction

    def test_decimal_precision_is_preserved(self) -> None:
        """Exact Decimal values must not be converted or rounded through binary float."""
        tx = BankTransaction(
            date=date(2026, 1, 10),
            description="Precision test",
            debit=Decimal("1234567.890123"),
            credit=Decimal("0.00"),
            balance=Decimal("9876543.210987"),
            source_row=12,
        )
        assert tx.debit == Decimal("1234567.890123")
        assert tx.balance == Decimal("9876543.210987")
        assert isinstance(tx.debit, Decimal)
        assert isinstance(tx.balance, Decimal)

    def test_negative_balance_is_allowed(self) -> None:
        """An account balance can be negative (e.g. overdraft or negative balance)."""
        tx = BankTransaction(
            date=date(2026, 1, 12),
            description="Overdraft fee",
            debit=Decimal("50.00"),
            credit=Decimal("0"),
            balance=Decimal("-150.75"),
            source_row=15,
        )
        assert tx.balance == Decimal("-150.75")

    def test_negative_debit_or_credit_rejected(self) -> None:
        """Debit and credit must be non-negative magnitudes (ge=0)."""
        with pytest.raises(ValidationError):
            BankTransaction(
                date=date(2026, 1, 1),
                description="Invalid negative debit",
                debit=Decimal("-10.00"),
                credit=Decimal("0"),
                balance=Decimal("100"),
                source_row=1,
            )

        with pytest.raises(ValidationError):
            BankTransaction(
                date=date(2026, 1, 1),
                description="Invalid negative credit",
                debit=Decimal("0"),
                credit=Decimal("-5.00"),
                balance=Decimal("100"),
                source_row=1,
            )

    def test_non_finite_amounts_rejected(self) -> None:
        """NaN and infinite amounts must be rejected."""
        for non_finite in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
            with pytest.raises(ValidationError):
                BankTransaction(
                    date=date(2026, 1, 1),
                    description="Non-finite test",
                    debit=non_finite,
                    credit=Decimal("0"),
                    balance=Decimal("100"),
                    source_row=1,
                )

    def test_source_row_must_be_positive_integer(self) -> None:
        """Source rows are 1-based positive integers."""
        with pytest.raises(ValidationError):
            BankTransaction(
                date=date(2026, 1, 1),
                description="Zero source row",
                debit=Decimal("10"),
                credit=Decimal("0"),
                balance=Decimal("100"),
                source_row=0,
            )

        with pytest.raises(ValidationError):
            BankTransaction(
                date=date(2026, 1, 1),
                description="Negative source row",
                debit=Decimal("10"),
                credit=Decimal("0"),
                balance=Decimal("100"),
                source_row=-5,
            )

    def test_missing_required_fields_raises_validation_error(self) -> None:
        """Required transaction fields must not be omitted."""
        with pytest.raises(ValidationError):
            BankTransaction.model_validate(
                {
                    "date": "2026-01-01",
                    "description": "Missing debit/credit/balance",
                    "source_row": 5,
                }
            )

    def test_duplicate_transactions_are_preserved(self) -> None:
        """Two identical payments with the same amount and date must not be collapsed."""
        tx1 = BankTransaction(
            date=date(2026, 1, 15),
            description="Recurring subscription",
            debit=Decimal("9.99"),
            credit=Decimal("0"),
            balance=Decimal("100.00"),
            source_row=10,
        )
        tx2 = BankTransaction(
            date=date(2026, 1, 15),
            description="Recurring subscription",
            debit=Decimal("9.99"),
            credit=Decimal("0"),
            balance=Decimal("90.01"),
            source_row=11,
        )
        statement = BankStatement(
            transactions=[tx1, tx2],
            source_metadata=SourceMetadata(
                document_id=UUID("00000000-0000-4000-8000-000000000001")
            ),
        )
        assert len(statement.transactions) == 2
        assert statement.transactions[0].source_row == 10
        assert statement.transactions[1].source_row == 11


class TestMetadataAndErrorHandling:
    """Tests currency code validation, source metadata/location shapes, and parser error hierarchy."""

    def test_currency_code_validation(self) -> None:
        """Currency must be a 3-letter alphabetic ISO code or None."""
        statement = BankStatement(
            currency="usd",
            transactions=[],
            source_metadata=SourceMetadata(
                document_id=UUID("00000000-0000-4000-8000-000000000001")
            ),
        )
        assert statement.currency == "USD"

        with pytest.raises(ValidationError):
            BankStatement(
                currency="US Dollar",
                transactions=[],
                source_metadata=SourceMetadata(
                    document_id=UUID("00000000-0000-4000-8000-000000000001")
                ),
            )

        with pytest.raises(ValidationError):
            BankStatement(
                currency="123",
                transactions=[],
                source_metadata=SourceMetadata(
                    document_id=UUID("00000000-0000-4000-8000-000000000001")
                ),
            )

    def test_unmapped_item_structure(self) -> None:
        """Unmapped preserves unknown content with location, label, value, and reason."""
        item = UnmappedItem(
            source_row=14,
            raw_label="Tax Deducted",
            raw_value="150.00",
            reason="unsupported_tax_line",
        )
        assert item.source_row == 14
        assert item.raw_label == "Tax Deducted"
        assert item.raw_value == "150.00"
        assert item.reason == "unsupported_tax_line"

    def test_source_location_structure(self) -> None:
        """SourceLocation encapsulates 1-based source row reference."""
        loc = SourceLocation(source_row=4)
        assert loc.source_row == 4
        with pytest.raises(ValidationError):
            SourceLocation(source_row=0)

    def test_parser_errors_hierarchy(self) -> None:
        """All parser exceptions inherit from BankStatementParserError and retain safe messages."""
        errors = [
            UnsupportedFormatError("Unsupported file extension .pdf"),
            InvalidStatementError("Missing required transaction headers"),
            AmbiguousWorksheetError("Multiple sheets match bank format"),
            ResourceLimitError("Exceeded 10000 transaction row limit"),
        ]
        for err in errors:
            assert isinstance(err, BankStatementParserError)
            assert isinstance(err, Exception)
            assert len(err.message) > 0


class TestPersistenceBoundaryCompatibility:
    """Verifies that model_dump(mode='python') output cleanly satisfies persistence boundaries."""

    def test_model_dump_python_preserves_decimals_and_dates(self) -> None:
        """Ensures mode='python' produces Decimals, dates, and UUIDs for DB persistence."""
        statement = BankStatement(
            bank="Test Bank",
            currency="INR",
            opening_balance=Decimal("5000.00"),
            closing_balance=Decimal("6000.00"),
            transactions=[
                BankTransaction(
                    date=date(2026, 1, 10),
                    description="Deposit",
                    debit=Decimal("0.00"),
                    credit=Decimal("1000.00"),
                    balance=Decimal("6000.00"),
                    source_row=5,
                )
            ],
            source_metadata=SourceMetadata(
                document_id=UUID("12345678-1234-5678-1234-567812345678"),
                sheet_name=None,
            ),
        )
        data = statement.model_dump(mode="python")

        assert isinstance(data["opening_balance"], Decimal)
        assert isinstance(data["closing_balance"], Decimal)
        assert isinstance(data["transactions"][0]["debit"], Decimal)
        assert isinstance(data["transactions"][0]["credit"], Decimal)
        assert isinstance(data["transactions"][0]["balance"], Decimal)
        assert isinstance(data["transactions"][0]["date"], date)
        assert isinstance(data["source_metadata"]["document_id"], UUID)

    def test_transaction_compatibility_with_db_record(self) -> None:
        """Tests that parsed transaction dict matches the TransactionRecord schema if present."""
        try:
            from app.db.models import TransactionRecord
        except ImportError:
            pytest.skip("app.db.models not available in current branch")

        doc_id = UUID("10000000-0000-4000-8000-000000000001")
        tx = BankTransaction(
            date=date(2026, 1, 5),
            description="Synthetic salary",
            debit=Decimal("0"),
            credit=Decimal("5000"),
            balance=Decimal("15000"),
            source_row=6,
        )
        tx_dict = tx.model_dump(mode="python")
        tx_dict["id"] = UUID("20000000-0000-4000-8000-000000000002")
        tx_dict["document_id"] = doc_id

        record = TransactionRecord.model_validate(tx_dict)
        assert record.debit == Decimal("0")
        assert record.credit == Decimal("5000")
        assert record.balance == Decimal("15000")
        assert record.source_row == 6
