"""Tests for bank statement KPI calculations and balance reconciliation."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from app.analysis.bank_kpis import (
    CALCULATION_ID_BALANCE_RECONCILIATION,
    CALCULATION_ID_CLOSING_BALANCE,
    CALCULATION_ID_NET_CASH_FLOW,
    CALCULATION_ID_OPENING_BALANCE,
    CALCULATION_ID_TOTAL_CREDIT,
    CALCULATION_ID_TOTAL_DEBIT,
    RELIABILITY_INSUFFICIENT_DATA,
    RELIABILITY_UNRELIABLE,
    RELIABILITY_VALID,
    STATUS_AVAILABLE,
    STATUS_UNAVAILABLE,
    WARNING_MISSING_CURRENCY,
    analyze_bank_statement,
    calculate_balance_reconciliation,
    calculate_bank_kpis,
    calculate_closing_balance,
    calculate_net_cash_flow,
    calculate_opening_balance,
    calculate_total_credit,
    calculate_total_debit,
    serialize_analysis_result,
)

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "contracts" / "examples"


@pytest.fixture
def synthetic_bank_statement() -> dict:
    """Load the shared synthetic bank statement contract example."""
    with open(FIXTURES_DIR / "bank-statement.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def synthetic_financial_analysis() -> dict:
    """Load the shared financial analysis contract example."""
    with open(FIXTURES_DIR / "financial-analysis.json", encoding="utf-8") as f:
        return json.load(f)


class TestSyntheticContractConformance:
    """Test calculations against the agreed synthetic contract examples."""

    def test_total_credit_conformance(self, synthetic_bank_statement: dict) -> None:
        metric = calculate_total_credit(synthetic_bank_statement)

        assert metric["key"] == "total_credit"
        assert metric["value"] == Decimal("5000")
        assert metric["value"] == 5000
        assert metric["unit"] == "INR"
        assert metric["status"] == STATUS_AVAILABLE
        assert metric["reason"] is None
        assert metric["calculation_id"] == CALCULATION_ID_TOTAL_CREDIT

        assert len(metric["source_refs"]) == 1
        ref = metric["source_refs"][0]
        assert ref["document_id"] == "10000000-0000-4000-8000-000000000001"
        assert ref["sheet_name"] is None
        assert ref["source_rows"] == [6]
        assert ref["field_paths"] == ["transactions[0].credit"]

    def test_total_debit_conformance(self, synthetic_bank_statement: dict) -> None:
        metric = calculate_total_debit(synthetic_bank_statement)

        assert metric["key"] == "total_debit"
        assert metric["value"] == Decimal("2500")
        assert metric["value"] == 2500
        assert metric["unit"] == "INR"
        assert metric["status"] == STATUS_AVAILABLE
        assert metric["reason"] is None
        assert metric["calculation_id"] == CALCULATION_ID_TOTAL_DEBIT

        assert len(metric["source_refs"]) == 1
        ref = metric["source_refs"][0]
        assert ref["document_id"] == "10000000-0000-4000-8000-000000000001"
        assert ref["sheet_name"] is None
        assert ref["source_rows"] == [7, 8]
        assert ref["field_paths"] == ["transactions[1].debit", "transactions[2].debit"]

    def test_net_cash_flow_conformance(self, synthetic_bank_statement: dict) -> None:
        metric = calculate_net_cash_flow(synthetic_bank_statement)

        assert metric["key"] == "net_cash_flow"
        assert metric["value"] == Decimal("2500")
        assert metric["value"] == 2500
        assert metric["unit"] == "INR"
        assert metric["status"] == STATUS_AVAILABLE
        assert metric["reason"] is None
        assert metric["calculation_id"] == CALCULATION_ID_NET_CASH_FLOW

        assert len(metric["source_refs"]) == 1
        ref = metric["source_refs"][0]
        assert ref["document_id"] == "10000000-0000-4000-8000-000000000001"
        assert ref["sheet_name"] is None
        assert ref["source_rows"] == [6, 7, 8]
        assert ref["field_paths"] == [
            "transactions[0].credit",
            "transactions[1].debit",
            "transactions[2].debit",
        ]

    def test_opening_balance_conformance(self, synthetic_bank_statement: dict) -> None:
        metric = calculate_opening_balance(synthetic_bank_statement)

        assert metric["key"] == "opening_balance"
        assert metric["value"] == Decimal("10000")
        assert metric["value"] == 10000
        assert metric["unit"] == "INR"
        assert metric["status"] == STATUS_AVAILABLE
        assert metric["reason"] is None
        assert metric["calculation_id"] == CALCULATION_ID_OPENING_BALANCE

        assert len(metric["source_refs"]) == 1
        ref = metric["source_refs"][0]
        assert ref["document_id"] == "10000000-0000-4000-8000-000000000001"
        assert ref["sheet_name"] is None
        assert ref["source_rows"] == [4]
        assert ref["field_paths"] == ["opening_balance"]

    def test_closing_balance_conformance(self, synthetic_bank_statement: dict) -> None:
        metric = calculate_closing_balance(synthetic_bank_statement)

        assert metric["key"] == "closing_balance"
        assert metric["value"] == Decimal("12500")
        assert metric["value"] == 12500
        assert metric["unit"] == "INR"
        assert metric["status"] == STATUS_AVAILABLE
        assert metric["reason"] is None
        assert metric["calculation_id"] == CALCULATION_ID_CLOSING_BALANCE

        assert len(metric["source_refs"]) == 1
        ref = metric["source_refs"][0]
        assert ref["document_id"] == "10000000-0000-4000-8000-000000000001"
        assert ref["sheet_name"] is None
        assert ref["source_rows"] == [9]
        assert ref["field_paths"] == ["closing_balance"]

    def test_balance_reconciliation_conformance(
        self, synthetic_bank_statement: dict
    ) -> None:
        metric = calculate_balance_reconciliation(synthetic_bank_statement)

        assert metric["key"] == "balance_reconciliation"
        assert metric["value"] == Decimal("0")
        assert metric["unit"] == "INR"
        assert metric["status"] == STATUS_AVAILABLE
        assert metric["reason"] is None
        assert metric["calculation_id"] == CALCULATION_ID_BALANCE_RECONCILIATION

        assert len(metric["source_refs"]) == 1
        ref = metric["source_refs"][0]
        assert ref["document_id"] == "10000000-0000-4000-8000-000000000001"
        assert ref["sheet_name"] is None
        assert ref["source_rows"] == [4, 6, 7, 8, 9]
        assert ref["field_paths"] == [
            "opening_balance",
            "transactions[0].credit",
            "transactions[1].debit",
            "transactions[2].debit",
            "closing_balance",
        ]

    def test_analyze_bank_statement_matches_fixture(
        self, synthetic_bank_statement: dict, synthetic_financial_analysis: dict
    ) -> None:
        result = analyze_bank_statement(
            synthetic_bank_statement,
            workspace_id="20000000-0000-4000-8000-000000000001",
        )

        assert result == synthetic_financial_analysis
        assert result["reliability"] == RELIABILITY_VALID
        assert result["warnings"] == []

    def test_analyze_with_optional_reconciliation_metric(
        self, synthetic_bank_statement: dict
    ) -> None:
        result = analyze_bank_statement(
            synthetic_bank_statement,
            workspace_id="20000000-0000-4000-8000-000000000001",
            include_reconciliation_metric=True,
        )

        assert len(result["metrics"]) == 4
        assert result["metrics"][3]["key"] == "balance_reconciliation"
        assert result["metrics"][3]["value"] == Decimal("0")

    def test_analyze_with_optional_balance_metrics(
        self, synthetic_bank_statement: dict
    ) -> None:
        result = analyze_bank_statement(
            synthetic_bank_statement,
            workspace_id="20000000-0000-4000-8000-000000000001",
            include_balance_metrics=True,
        )

        assert len(result["metrics"]) == 5
        keys = [m["key"] for m in result["metrics"]]
        assert keys == [
            "total_credit",
            "total_debit",
            "net_cash_flow",
            "opening_balance",
            "closing_balance",
        ]


class TestOpeningAndClosingBalances:
    """Verify calculate_opening_balance and calculate_closing_balance behavior."""

    def test_missing_opening_balance_metric(self) -> None:
        statement = {
            "currency": "INR",
            "closing_balance": 1000,
        }
        metric = calculate_opening_balance(statement)
        assert metric["status"] == STATUS_UNAVAILABLE
        assert metric["value"] is None
        assert "Missing required 'opening_balance'" in metric["reason"]

    def test_missing_closing_balance_metric(self) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": 1000,
        }
        metric = calculate_closing_balance(statement)
        assert metric["status"] == STATUS_UNAVAILABLE
        assert metric["value"] is None
        assert "Missing required 'closing_balance'" in metric["reason"]

    def test_invalid_opening_balance_metric(self) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": "not-a-number",
            "closing_balance": 1000,
        }
        metric = calculate_opening_balance(statement)
        assert metric["status"] == STATUS_UNAVAILABLE
        assert metric["value"] is None
        assert "Invalid non-numeric 'opening_balance'" in metric["reason"]

    def test_invalid_closing_balance_metric(self) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": 1000,
            "closing_balance": "corrupted",
        }
        metric = calculate_closing_balance(statement)
        assert metric["status"] == STATUS_UNAVAILABLE
        assert metric["value"] is None
        assert "Invalid non-numeric 'closing_balance'" in metric["reason"]

    def test_source_locations_omitted_opening_closing(self) -> None:
        statement = {
            "currency": "USD",
            "opening_balance": 500,
            "closing_balance": 750,
        }
        op = calculate_opening_balance(statement)
        assert op["status"] == STATUS_AVAILABLE
        assert op["value"] == Decimal("500")
        assert op["source_refs"][0]["source_rows"] == []
        assert op["source_refs"][0]["field_paths"] == ["opening_balance"]

        cl = calculate_closing_balance(statement)
        assert cl["status"] == STATUS_AVAILABLE
        assert cl["value"] == Decimal("750")
        assert cl["source_refs"][0]["source_rows"] == []
        assert cl["source_refs"][0]["field_paths"] == ["closing_balance"]


class TestMissingCurrencyPolicy:
    """Verify that unknown currency blocks affected monetary KPIs and sets reliability."""

    def test_missing_currency_blocks_total_credit(
        self, synthetic_bank_statement: dict
    ) -> None:
        statement = json.loads(json.dumps(synthetic_bank_statement))
        statement["currency"] = None

        credit = calculate_total_credit(statement)
        assert credit["status"] == STATUS_UNAVAILABLE
        assert credit["value"] is None
        assert credit["unit"] is None
        assert credit["reason"] == WARNING_MISSING_CURRENCY
        # Preserves source references to the contributing transactions
        assert credit["source_refs"][0]["source_rows"] == [6]
        assert credit["source_refs"][0]["field_paths"] == ["transactions[0].credit"]

    def test_missing_currency_blocks_all_monetary_metrics(
        self, synthetic_bank_statement: dict
    ) -> None:
        statement = json.loads(json.dumps(synthetic_bank_statement))
        statement["currency"] = ""  # empty string

        debit = calculate_total_debit(statement)
        assert debit["status"] == STATUS_UNAVAILABLE
        assert debit["reason"] == WARNING_MISSING_CURRENCY
        assert debit["source_refs"][0]["source_rows"] == [7, 8]

        net = calculate_net_cash_flow(statement)
        assert net["status"] == STATUS_UNAVAILABLE
        assert net["reason"] == WARNING_MISSING_CURRENCY

        op = calculate_opening_balance(statement)
        assert op["status"] == STATUS_UNAVAILABLE
        assert op["reason"] == WARNING_MISSING_CURRENCY
        assert op["source_refs"][0]["source_rows"] == [4]

        cl = calculate_closing_balance(statement)
        assert cl["status"] == STATUS_UNAVAILABLE
        assert cl["reason"] == WARNING_MISSING_CURRENCY
        assert cl["source_refs"][0]["source_rows"] == [9]

        recon = calculate_balance_reconciliation(statement)
        assert recon["status"] == STATUS_UNAVAILABLE
        assert recon["reason"] == WARNING_MISSING_CURRENCY

    def test_analyze_bank_statement_missing_currency_sets_insufficient_data(
        self, synthetic_bank_statement: dict
    ) -> None:
        statement = json.loads(json.dumps(synthetic_bank_statement))
        del statement["currency"]

        result = analyze_bank_statement(statement)
        assert result["currency"] is None
        assert result["reliability"] == RELIABILITY_INSUFFICIENT_DATA
        assert WARNING_MISSING_CURRENCY in result["warnings"]
        assert all(m["status"] == STATUS_UNAVAILABLE for m in result["metrics"])
        assert all(m["unit"] is None for m in result["metrics"])


class TestCommaSeparatedNumberStrings:
    """Verify support for International and Indian grouping formats and rejection of malformed numbers."""

    @pytest.mark.parametrize(
        ("val_str", "expected_decimal"),
        [
            ("1,500.00", Decimal("1500.00")),
            ("1,000,000.00", Decimal("1000000.00")),
            ("123,456,789.25", Decimal("123456789.25")),
            ("1,500", Decimal("1500")),
        ],
    )
    def test_valid_international_grouping(
        self, val_str: str, expected_decimal: Decimal
    ) -> None:
        statement = {
            "currency": "USD",
            "opening_balance": val_str,
            "closing_balance": val_str,
            "transactions": [{"credit": val_str, "debit": "0.00", "source_row": 2}],
        }
        op = calculate_opening_balance(statement)
        assert op["status"] == STATUS_AVAILABLE
        assert op["value"] == expected_decimal

        credit = calculate_total_credit(statement)
        assert credit["status"] == STATUS_AVAILABLE
        assert credit["value"] == expected_decimal

    @pytest.mark.parametrize(
        ("val_str", "expected_decimal"),
        [
            ("1,50,000.00", Decimal("150000.00")),
            ("10,00,000.50", Decimal("1000000.50")),
            ("1,00,00,000", Decimal("10000000")),
            ("12,34,56,789.50", Decimal("123456789.50")),
        ],
    )
    def test_valid_indian_grouping(
        self, val_str: str, expected_decimal: Decimal
    ) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": val_str,
            "closing_balance": val_str,
            "transactions": [{"credit": val_str, "debit": 0, "source_row": 2}],
        }
        op = calculate_opening_balance(statement)
        assert op["status"] == STATUS_AVAILABLE
        assert op["value"] == expected_decimal

        credit = calculate_total_credit(statement)
        assert credit["status"] == STATUS_AVAILABLE
        assert credit["value"] == expected_decimal

    @pytest.mark.parametrize(
        ("val_str", "expected_decimal"),
        [
            ("-1,500.00", Decimal("-1500.00")),
            ("-1,50,000.00", Decimal("-150000.00")),
            ("-10,00,000.50", Decimal("-1000000.50")),
        ],
    )
    def test_valid_negative_grouped_balances(
        self, val_str: str, expected_decimal: Decimal
    ) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": val_str,
            "closing_balance": val_str,
            "transactions": [],
        }
        op = calculate_opening_balance(statement)
        assert op["status"] == STATUS_AVAILABLE
        assert op["value"] == expected_decimal

        cl = calculate_closing_balance(statement)
        assert cl["status"] == STATUS_AVAILABLE
        assert cl["value"] == expected_decimal

    @pytest.mark.parametrize(
        "malformed_str",
        [
            "1,00",
            "1,0000",
            "100,",
            ",100",
            "1,000,00",
            "1,50,00",
            "1,2,3",
            "1,500.0,0",
            "1.2.3",
            "1,,000",
            "1,50,000,00.00",
            "1,2345.00",
        ],
    )
    def test_rejected_malformed_grouping_strings(self, malformed_str: str) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": malformed_str,
            "transactions": [{"credit": malformed_str, "debit": 0, "source_row": 2}],
        }
        op = calculate_opening_balance(statement)
        assert op["status"] == STATUS_UNAVAILABLE
        assert op["value"] is None

        credit = calculate_total_credit(statement)
        assert credit["status"] == STATUS_UNAVAILABLE
        assert credit["value"] is None


class TestEmptyTransactionsPolicy:
    """Verify behavior with zero transactions under various balance and currency conditions."""

    def test_empty_transactions_matching_balances_valid_analysis(self) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": "5,000.00",
            "closing_balance": "5,000.00",
            "transactions": [],
        }
        result = analyze_bank_statement(statement)

        assert result["reliability"] == RELIABILITY_VALID
        assert result["warnings"] == []
        assert result["metrics"][0]["key"] == "total_credit"
        assert result["metrics"][0]["value"] == Decimal("0")
        assert result["metrics"][0]["status"] == STATUS_AVAILABLE
        assert result["metrics"][1]["key"] == "total_debit"
        assert result["metrics"][1]["value"] == Decimal("0")
        assert result["metrics"][2]["key"] == "net_cash_flow"
        assert result["metrics"][2]["value"] == Decimal("0")

    def test_empty_transactions_missing_opening_balance(self) -> None:
        statement = {
            "currency": "INR",
            "closing_balance": 5000,
            "transactions": [],
        }
        result = analyze_bank_statement(statement)
        assert result["reliability"] == RELIABILITY_INSUFFICIENT_DATA
        assert any("opening_balance" in w for w in result["warnings"])

    def test_empty_transactions_missing_closing_balance(self) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": 5000,
            "transactions": [],
        }
        result = analyze_bank_statement(statement)
        assert result["reliability"] == RELIABILITY_INSUFFICIENT_DATA
        assert any("closing_balance" in w for w in result["warnings"])

    def test_empty_transactions_mismatching_balances_unreliable(self) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": "5,000.00",
            "closing_balance": "6,000.00",
            "transactions": [],
        }
        result = analyze_bank_statement(statement)

        assert result["reliability"] == RELIABILITY_UNRELIABLE
        assert len(result["warnings"]) == 1
        assert "mismatch" in result["warnings"][0].lower()

    def test_missing_transactions_not_silently_fabricated(self) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": 5000,
            "closing_balance": 5000,
            # No transactions key
        }
        result = analyze_bank_statement(statement)
        assert result["reliability"] == RELIABILITY_INSUFFICIENT_DATA
        assert any("Missing required 'transactions'" in w for w in result["warnings"])


class TestReconciliationReliabilityPolicy:
    """Verify that reconciliation is evaluated for reliability even when metric is excluded."""

    def test_reconciliation_evaluated_for_reliability_when_metric_excluded(
        self, synthetic_bank_statement: dict
    ) -> None:
        tampered = json.loads(json.dumps(synthetic_bank_statement))
        tampered["closing_balance"] = 13000  # Discrepancy of -500

        result = analyze_bank_statement(tampered, include_reconciliation_metric=False)

        assert len(result["metrics"]) == 3
        assert [m["key"] for m in result["metrics"]] == [
            "total_credit",
            "total_debit",
            "net_cash_flow",
        ]
        assert result["reliability"] == RELIABILITY_UNRELIABLE
        assert len(result["warnings"]) == 1
        assert "mismatch" in result["warnings"][0].lower()

    def test_reconciliation_valid_reliability_when_metric_excluded(
        self, synthetic_bank_statement: dict
    ) -> None:
        result = analyze_bank_statement(
            synthetic_bank_statement, include_reconciliation_metric=False
        )

        assert len(result["metrics"]) == 3
        assert result["reliability"] == RELIABILITY_VALID
        assert result["warnings"] == []


class TestSourceRowValidation:
    """Verify strict validation of source_row as 1-based positive integers."""

    @pytest.mark.parametrize("invalid_row", [0, -1, -100, "5", True, False, 2.5])
    def test_invalid_source_row_in_transaction_credit(
        self, invalid_row: object
    ) -> None:
        statement = {
            "currency": "INR",
            "transactions": [
                {"credit": 1000, "debit": 0, "source_row": invalid_row},
            ],
        }
        credit = calculate_total_credit(statement)
        assert credit["status"] == STATUS_UNAVAILABLE
        assert credit["value"] is None
        assert "positive integer" in credit["reason"]

    @pytest.mark.parametrize("invalid_row", [0, -1, -50, "10", True, False, 3.14])
    def test_invalid_source_row_in_transaction_debit(self, invalid_row: object) -> None:
        statement = {
            "currency": "INR",
            "transactions": [
                {"credit": 0, "debit": 500, "source_row": invalid_row},
            ],
        }
        debit = calculate_total_debit(statement)
        assert debit["status"] == STATUS_UNAVAILABLE
        assert debit["value"] is None
        assert "positive integer" in debit["reason"]

    def test_valid_positive_source_rows_accepted(self) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": 1000,
            "closing_balance": 1500,
            "source_locations": {
                "opening_balance": {"source_row": 1},
                "closing_balance": {"source_row": 5},
            },
            "transactions": [
                {"credit": 500, "debit": 0, "source_row": 2},
                {"credit": 0, "debit": 0, "source_row": 3},
            ],
        }
        credit = calculate_total_credit(statement)
        assert credit["status"] == STATUS_AVAILABLE
        assert credit["source_refs"][0]["source_rows"] == [2]

        recon = calculate_balance_reconciliation(statement)
        assert recon["status"] == STATUS_AVAILABLE
        assert recon["source_refs"][0]["source_rows"] == [1, 2, 5]


class TestNaNAndInfinityHandling:
    """Verify that Decimal NaN, Decimal Infinity, float NaN, and float Infinity are rejected."""

    @pytest.mark.parametrize(
        "invalid_val",
        [
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
            float("nan"),
            float("inf"),
            float("-inf"),
            "NaN",
            "Infinity",
            "-Infinity",
            "-inf",
        ],
    )
    def test_nan_and_infinity_in_credit_rejected(self, invalid_val: object) -> None:
        statement = {
            "currency": "INR",
            "transactions": [{"credit": invalid_val, "debit": 0, "source_row": 2}],
        }
        credit = calculate_total_credit(statement)
        assert credit["status"] == STATUS_UNAVAILABLE
        assert credit["value"] is None

    @pytest.mark.parametrize(
        "invalid_val",
        [
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
            float("nan"),
            float("inf"),
            float("-inf"),
            "NaN",
            "Infinity",
            "-Infinity",
            "-inf",
        ],
    )
    def test_nan_and_infinity_in_debit_rejected(self, invalid_val: object) -> None:
        statement = {
            "currency": "INR",
            "transactions": [{"credit": 0, "debit": invalid_val, "source_row": 2}],
        }
        debit = calculate_total_debit(statement)
        assert debit["status"] == STATUS_UNAVAILABLE
        assert debit["value"] is None

    @pytest.mark.parametrize(
        "invalid_val",
        [
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
            float("nan"),
            float("inf"),
            float("-inf"),
        ],
    )
    def test_nan_and_infinity_in_opening_closing_balances_rejected(
        self, invalid_val: object
    ) -> None:
        statement_open = {
            "currency": "INR",
            "opening_balance": invalid_val,
            "closing_balance": 1000,
            "transactions": [{"credit": 0, "debit": 0, "source_row": 2}],
        }
        recon_open = calculate_balance_reconciliation(statement_open)
        assert recon_open["status"] == STATUS_UNAVAILABLE
        assert recon_open["value"] is None

        statement_close = {
            "currency": "INR",
            "opening_balance": 1000,
            "closing_balance": invalid_val,
            "transactions": [{"credit": 0, "debit": 0, "source_row": 2}],
        }
        recon_close = calculate_balance_reconciliation(statement_close)
        assert recon_close["status"] == STATUS_UNAVAILABLE
        assert recon_close["value"] is None


class TestSourceLocationsRobustness:
    """Verify safe handling when source_locations or nested values have unexpected types."""

    @pytest.mark.parametrize("bad_locations", ["string_loc", [1, 2, 3], 123, True])
    def test_source_locations_top_level_unexpected_type(
        self, bad_locations: object
    ) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": 1000,
            "closing_balance": 1000,
            "source_locations": bad_locations,
            "transactions": [],
        }
        recon = calculate_balance_reconciliation(statement)
        assert recon["status"] == STATUS_UNAVAILABLE
        assert recon["value"] is None
        assert "Expected 'source_locations' to be a dict" in recon["reason"]

    @pytest.mark.parametrize("bad_loc", ["invalid_nested", [1], 99, True])
    def test_source_locations_nested_unexpected_type(self, bad_loc: object) -> None:
        statement_open = {
            "currency": "INR",
            "opening_balance": 1000,
            "closing_balance": 1000,
            "source_locations": {"opening_balance": bad_loc},
            "transactions": [],
        }
        recon = calculate_balance_reconciliation(statement_open)
        assert recon["status"] == STATUS_UNAVAILABLE
        assert (
            "Expected 'source_locations.opening_balance' to be a dict"
            in recon["reason"]
        )

        statement_close = {
            "currency": "INR",
            "opening_balance": 1000,
            "closing_balance": 1000,
            "source_locations": {"closing_balance": bad_loc},
            "transactions": [],
        }
        recon_close = calculate_balance_reconciliation(statement_close)
        assert recon_close["status"] == STATUS_UNAVAILABLE
        assert (
            "Expected 'source_locations.closing_balance' to be a dict"
            in recon_close["reason"]
        )

    @pytest.mark.parametrize("bad_row", [0, -1, "row4", True, False, 4.5])
    def test_source_locations_nested_row_invalid(self, bad_row: object) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": 1000,
            "closing_balance": 1000,
            "source_locations": {"opening_balance": {"source_row": bad_row}},
            "transactions": [],
        }
        recon = calculate_balance_reconciliation(statement)
        assert recon["status"] == STATUS_UNAVAILABLE
        assert "positive integer" in recon["reason"]

    def test_source_locations_omitted_or_none_safe(self) -> None:
        statement_none = {
            "currency": "INR",
            "opening_balance": 1000,
            "closing_balance": 1000,
            "source_locations": None,
            "transactions": [],
        }
        recon = calculate_balance_reconciliation(statement_none)
        assert recon["status"] == STATUS_AVAILABLE
        assert recon["source_refs"][0]["source_rows"] == []
        assert recon["source_refs"][0]["field_paths"] == [
            "opening_balance",
            "closing_balance",
        ]


class TestFastApiSerializationAndPrecision:
    """Verify that results serialize cleanly through FastAPI without losing financial precision."""

    def test_jsonable_encoder_matches_financial_analysis_fixture(
        self, synthetic_bank_statement: dict, synthetic_financial_analysis: dict
    ) -> None:
        result = analyze_bank_statement(
            synthetic_bank_statement,
            workspace_id="20000000-0000-4000-8000-000000000001",
        )
        encoded = jsonable_encoder(result)

        assert encoded == synthetic_financial_analysis
        assert isinstance(encoded["metrics"][0]["value"], int)
        assert encoded["metrics"][0]["value"] == 5000

    def test_fastapi_http_route_serialization(
        self, synthetic_bank_statement: dict, synthetic_financial_analysis: dict
    ) -> None:
        app = FastAPI()

        @app.get("/api/analysis")
        def get_analysis() -> dict:
            result = analyze_bank_statement(
                synthetic_bank_statement,
                workspace_id="20000000-0000-4000-8000-000000000001",
            )
            return serialize_analysis_result(result)

        client = TestClient(app)
        response = client.get("/api/analysis")

        assert response.status_code == 200
        assert response.json() == synthetic_financial_analysis

    def test_exact_paise_and_cent_precision_serialized(self) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": "1000.50",
            "closing_balance": "1250.75",
            "transactions": [
                {"credit": "300.50", "debit": "0.00", "source_row": 2},
                {"credit": "0.00", "debit": "50.25", "source_row": 3},
            ],
            "source_locations": {
                "opening_balance": {"source_row": 1},
                "closing_balance": {"source_row": 4},
            },
        }
        result = analyze_bank_statement(statement, workspace_id="ws-precision")
        encoded = jsonable_encoder(result)

        assert encoded["reliability"] == RELIABILITY_VALID
        assert encoded["metrics"][0]["value"] == 300.5
        assert encoded["metrics"][1]["value"] == 50.25
        assert encoded["metrics"][2]["value"] == 250.25


class TestDecimalPrecision:
    """Verify that calculations preserve financial precision using Decimal."""

    def test_float_binary_imprecision_avoided(self) -> None:
        statement = {
            "currency": "USD",
            "opening_balance": "100.00",
            "closing_balance": "100.30",
            "transactions": [
                {"credit": "0.10", "debit": "0.00", "source_row": 2},
                {"credit": "0.20", "debit": "0.00", "source_row": 3},
            ],
            "source_metadata": {"document_id": "doc-float-test", "sheet_name": None},
            "source_locations": {
                "opening_balance": {"source_row": 1},
                "closing_balance": {"source_row": 4},
            },
        }

        credit = calculate_total_credit(statement)
        assert credit["value"] == Decimal("0.30")

        net = calculate_net_cash_flow(statement, credit)
        assert net["value"] == Decimal("0.30")

        recon = calculate_balance_reconciliation(statement, credit)
        assert recon["value"] == Decimal("0.00")
        assert recon["reason"] is None

    def test_negative_net_cash_flow(self) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": 10000,
            "closing_balance": 5000,
            "transactions": [
                {"credit": 2000, "debit": 0, "source_row": 2},
                {"credit": 0, "debit": 7000, "source_row": 3},
            ],
        }

        net = calculate_net_cash_flow(statement)
        assert net["value"] == Decimal("-5000")

        recon = calculate_balance_reconciliation(statement)
        assert recon["value"] == Decimal("0")


class TestBalanceReconciliationDiscrepancies:
    """Test behavior when statement balances do not reconcile."""

    def test_mismatched_closing_balance(self, synthetic_bank_statement: dict) -> None:
        tampered = json.loads(json.dumps(synthetic_bank_statement))
        tampered["closing_balance"] = 13000

        recon = calculate_balance_reconciliation(tampered)
        assert recon["status"] == STATUS_AVAILABLE
        assert recon["value"] == Decimal("-500")
        assert recon["reason"] is not None
        assert "mismatch" in recon["reason"].lower()

        analysis = analyze_bank_statement(tampered)
        assert analysis["reliability"] == RELIABILITY_UNRELIABLE
        assert len(analysis["warnings"]) == 1
        assert "mismatch" in analysis["warnings"][0].lower()

    def test_negative_balance_overdraft_reconciliation(self) -> None:
        statement = {
            "currency": "EUR",
            "opening_balance": -1000,
            "closing_balance": -600,
            "transactions": [
                {"credit": 500, "debit": 0, "source_row": 2},
                {"credit": 0, "debit": 100, "source_row": 3},
            ],
            "source_locations": {
                "opening_balance": {"source_row": 1},
                "closing_balance": {"source_row": 4},
            },
        }
        recon = calculate_balance_reconciliation(statement)
        assert recon["value"] == Decimal("0")
        assert recon["status"] == STATUS_AVAILABLE

        analysis = analyze_bank_statement(statement)
        assert analysis["reliability"] == RELIABILITY_VALID
        assert analysis["warnings"] == []


class TestSafeMissingAndInvalidDataHandling:
    """Verify that missing/invalid data is handled safely without silent zeros."""

    def test_missing_transactions_field(self) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": 1000,
            "closing_balance": 1000,
        }

        credit = calculate_total_credit(statement)
        assert credit["status"] == STATUS_UNAVAILABLE
        assert credit["value"] is None
        assert "Missing" in credit["reason"]

        debit = calculate_total_debit(statement)
        assert debit["status"] == STATUS_UNAVAILABLE
        assert debit["value"] is None

        net = calculate_net_cash_flow(statement)
        assert net["status"] == STATUS_UNAVAILABLE
        assert net["value"] is None

    def test_missing_credit_field_in_transaction(self) -> None:
        statement = {
            "currency": "INR",
            "transactions": [
                {"debit": 100, "source_row": 5},
            ],
        }

        credit = calculate_total_credit(statement)
        assert credit["status"] == STATUS_UNAVAILABLE
        assert credit["value"] is None
        assert "missing required 'credit' field" in credit["reason"].lower()

    def test_null_debit_field_in_transaction(self) -> None:
        statement = {
            "currency": "INR",
            "transactions": [
                {"credit": 100, "debit": None, "source_row": 5},
            ],
        }

        debit = calculate_total_debit(statement)
        assert debit["status"] == STATUS_UNAVAILABLE
        assert debit["value"] is None
        assert "missing required 'debit' field" in debit["reason"].lower()

    def test_invalid_string_amount(self) -> None:
        statement = {
            "currency": "INR",
            "transactions": [
                {"credit": "invalid_number", "debit": 0, "source_row": 5},
            ],
        }

        credit = calculate_total_credit(statement)
        assert credit["status"] == STATUS_UNAVAILABLE
        assert credit["value"] is None
        assert "invalid non-numeric credit" in credit["reason"].lower()

    def test_negative_credit_rejected(self) -> None:
        statement = {
            "currency": "INR",
            "transactions": [
                {"credit": -500, "debit": 0, "source_row": 5},
            ],
        }

        credit = calculate_total_credit(statement)
        assert credit["status"] == STATUS_UNAVAILABLE
        assert credit["value"] is None
        assert "negative credit magnitude" in credit["reason"].lower()

    def test_missing_opening_or_closing_balance(self) -> None:
        statement = {
            "currency": "INR",
            "transactions": [{"credit": 100, "debit": 50, "source_row": 2}],
        }

        recon = calculate_balance_reconciliation(statement)
        assert recon["status"] == STATUS_UNAVAILABLE
        assert recon["value"] is None
        assert "Missing required balance field(s)" in recon["reason"]

        analysis = analyze_bank_statement(statement)
        assert analysis["reliability"] == RELIABILITY_INSUFFICIENT_DATA
        assert len(analysis["warnings"]) > 0

    def test_empty_transactions_list(self) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": 5000,
            "closing_balance": 5000,
            "transactions": [],
        }

        credit = calculate_total_credit(statement)
        assert credit["status"] == STATUS_AVAILABLE
        assert credit["value"] == Decimal("0")
        assert credit["source_refs"][0]["source_rows"] == []

        debit = calculate_total_debit(statement)
        assert debit["status"] == STATUS_AVAILABLE
        assert debit["value"] == Decimal("0")

        net = calculate_net_cash_flow(statement)
        assert net["status"] == STATUS_AVAILABLE
        assert net["value"] == Decimal("0")

        recon = calculate_balance_reconciliation(statement)
        assert recon["status"] == STATUS_AVAILABLE
        assert recon["value"] == Decimal("0")

        analysis = analyze_bank_statement(statement)
        assert analysis["reliability"] == RELIABILITY_VALID


class TestTraceabilityAndSheetHandling:
    """Verify source reference preservation for multi-row and Excel sheets."""

    def test_sheet_name_preserved(self) -> None:
        statement = {
            "currency": "INR",
            "opening_balance": 1000,
            "closing_balance": 1500,
            "source_metadata": {
                "document_id": "custom-doc-id-123",
                "sheet_name": "Account Statement",
            },
            "source_locations": {
                "opening_balance": {"source_row": 2},
                "closing_balance": {"source_row": 10},
            },
            "transactions": [
                {"credit": 500, "debit": 0, "source_row": 6},
            ],
        }

        credit = calculate_total_credit(statement)
        ref = credit["source_refs"][0]
        assert ref["document_id"] == "custom-doc-id-123"
        assert ref["sheet_name"] == "Account Statement"
        assert ref["source_rows"] == [6]
        assert ref["field_paths"] == ["transactions[0].credit"]

        recon = calculate_balance_reconciliation(statement)
        ref_recon = recon["source_refs"][0]
        assert ref_recon["document_id"] == "custom-doc-id-123"
        assert ref_recon["sheet_name"] == "Account Statement"
        assert ref_recon["source_rows"] == [2, 6, 10]
        assert ref_recon["field_paths"] == [
            "opening_balance",
            "transactions[0].credit",
            "closing_balance",
        ]

    def test_calculate_bank_kpis_convenience_function(
        self, synthetic_bank_statement: dict
    ) -> None:
        kpis = calculate_bank_kpis(synthetic_bank_statement)
        assert len(kpis) == 3
        assert [k["key"] for k in kpis] == [
            "total_credit",
            "total_debit",
            "net_cash_flow",
        ]

        kpis_with_recon = calculate_bank_kpis(
            synthetic_bank_statement, include_reconciliation_metric=True
        )
        assert len(kpis_with_recon) == 4
        assert kpis_with_recon[3]["key"] == "balance_reconciliation"

        kpis_with_all = calculate_bank_kpis(
            synthetic_bank_statement,
            include_reconciliation_metric=True,
            include_balance_metrics=True,
        )
        assert len(kpis_with_all) == 6
        assert [k["key"] for k in kpis_with_all] == [
            "total_credit",
            "total_debit",
            "net_cash_flow",
            "opening_balance",
            "closing_balance",
            "balance_reconciliation",
        ]
