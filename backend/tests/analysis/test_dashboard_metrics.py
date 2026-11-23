"""Dashboard calculations over synthetic validated saved statements."""

import json
from datetime import date, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import UUID

import pytest

from app.analysis.dashboard_metrics import (
    balance_dashboard_metrics,
    bank_dashboard_metrics,
)
from app.db.parsed_models import ParsedBankStatement
from app.db.parsed_read_models import ParsedBalanceSheet
from app.parsers.balance_sheet import parse_balance_sheet

ROOT = Path(__file__).resolve().parents[3]
DOCUMENT = UUID("30000000-0000-4000-8000-000000000009")


def bank(rows=None, **changes):
    if rows is None:
        rows = [
            ("2026-01-01", "Synthetic salary", "0", "10", "110", 6),
            ("2026-01-03", "Synthetic groceries", "20", "0", "90", 7),
        ]
    transactions = [
        dict(
            date=day,
            description=description,
            debit=Decimal(debit),
            credit=Decimal(credit),
            balance=Decimal(balance),
            source_row=row,
        )
        for day, description, debit, credit, balance, row in rows
    ]
    data = {
        "bank": None,
        "account_holder": None,
        "account_type": None,
        "currency": "INR",
        "period_start": "2026-01-01",
        "period_end": "2026-01-05",
        "opening_balance": Decimal(100),
        "closing_balance": Decimal(90),
        "transactions": transactions,
        "unmapped": [],
        "source_metadata": {"document_id": DOCUMENT, "sheet_name": None},
        "source_locations": {
            "currency": {"source_row": 1},
            "period_start": {"source_row": 2},
            "period_end": {"source_row": 2},
            "opening_balance": {"source_row": 3},
            "closing_balance": {"source_row": 9},
        },
    }
    return ParsedBankStatement.model_validate(data | changes)


def balance(**changes):
    path = ROOT / "contracts/examples/balance-sheet.json"
    data = json.loads(path.read_text(), parse_float=Decimal)
    data["source_metadata"]["document_id"] = DOCUMENT
    return ParsedBalanceSheet.model_validate(data | changes)


def chart(result, key):
    return next(item for item in result["charts"] if item["key"] == key)


def metric(result):
    return result["metrics"][0]


def test_average_balance_weights_calendar_days_and_carries_verified_end_of_day():
    result = bank_dashboard_metrics(bank())
    assert metric(result)["value"] == 98  # (110*2 + 90*3) / 5
    assert metric(result)["calculation_id"] == "dashboard.average_balance.v1"
    points = chart(result, "daily_balances")["series"][0]["points"]
    assert [(point["label"], point["value"]) for point in points] == [
        ("2026-01-01", 110),
        ("2026-01-03", 90),
        ("2026-01-05", 90),
    ]
    refs = metric(result)["source_refs"][0]
    assert refs["document_id"] == str(DOCUMENT)
    assert refs["source_rows"] == [2, 3, 6, 7, 9]
    assert "period_start" in refs["field_paths"]
    assert "transactions[1].balance" in refs["field_paths"]


@pytest.mark.parametrize("reverse", [False, True])
def test_same_day_order_requires_running_balance_evidence(reverse):
    rows = [
        ("2026-01-01", "Deposit", "0", "10", "110", 6),
        ("2026-01-01", "Purchase", "20", "0", "90", 7),
    ]
    if reverse:
        rows = [(*row[:-1], 13 - row[-1]) for row in rows]
    result = bank_dashboard_metrics(bank(rows))
    assert metric(result)["value"] == 90


def test_unsorted_unique_dates_use_dates_and_preserve_original_field_paths():
    statement = bank()
    statement.transactions.reverse()
    result = bank_dashboard_metrics(statement)
    assert metric(result)["value"] == 98
    points = chart(result, "daily_flows")["series"][0]["points"]
    assert points[0]["source_refs"][0]["field_paths"] == [
        "transactions[1].date",
        "transactions[1].credit",
    ]


@pytest.mark.parametrize(
    "change",
    [
        "ambiguous",
        "broken_running_balance",
        "outside_period",
        "missing_opening",
        "missing_end",
        "missing_currency",
    ],
)
def test_unproven_daily_balances_are_unavailable(change):
    statement = bank()
    if change == "ambiguous":
        statement = bank(
            [
                ("2026-01-01", "Note A", "0", "0", "100", 6),
                ("2026-01-01", "Note B", "0", "0", "100", 7),
            ],
            closing_balance=Decimal(100),
        )
    elif change == "broken_running_balance":
        statement.transactions[0].balance = Decimal(999)
    elif change == "outside_period":
        statement.period_start = date(2026, 1, 2)
    elif change == "missing_opening":
        statement.opening_balance = None
    elif change == "missing_end":
        statement.period_end = None
    else:
        statement.currency = None
    result = bank_dashboard_metrics(statement)
    assert metric(result)["status"] == "unavailable"
    assert metric(result)["value"] is None and metric(result)["reason"]
    assert chart(result, "daily_balances")["series"] == []
    if change == "missing_currency":
        assert result["largest_inflows"] == []
        assert all(item["unit"] == "unknown" for item in result["charts"])
    else:
        assert chart(result, "daily_flows")["status"] == "available"


def test_flow_charts_group_all_dates_and_months_without_inventing_gap_values():
    statement = bank(
        [
            ("2026-01-02", "Salary", "0", "10", "110", 6),
            ("2026-01-02", "Groceries", "2.25", "0", "107.75", 7),
            ("2026-03-03", "Transfer", "0", "5.50", "113.25", 8),
        ],
        period_start="2026-01-02",
        period_end="2026-03-03",
        closing_balance=Decimal("113.25"),
    )
    result = bank_dashboard_metrics(statement)
    monthly = chart(result, "monthly_flows")
    assert [point["label"] for point in monthly["series"][0]["points"]] == [
        "2026-01",
        "2026-03",
    ]
    assert [point["value"] for point in monthly["series"][2]["points"]] == [
        Decimal("7.75"),
        Decimal("5.50"),
    ]
    assert "partial" in monthly["reason"] and "gaps" in monthly["reason"]
    assert monthly["series"][0]["points"][0]["source_refs"][0]["source_rows"] == [6, 7]
    assert [
        point["label"] for point in chart(result, "daily_flows")["series"][0]["points"]
    ] == [
        "2026-01-02",
        "2026-03-03",
    ]


def test_empty_bank_has_no_manufactured_history_or_rankings():
    result = bank_dashboard_metrics(bank([], closing_balance=Decimal(100)))
    assert metric(result)["value"] is None
    assert result["largest_inflows"] == result["largest_outflows"] == []
    assert all(item["series"] == [] for item in result["charts"])


def test_category_keyword_precedence_word_boundaries_and_debit_reconciliation():
    descriptions = [
        "rent grocery",
        "rent",
        "UPI",
        "current account",
        "ATM transfer",
        "college metro",
        "salary transfer",
    ]
    rows = [
        ("2026-01-01", description, str(index + 1), "0", "0", index + 6)
        for index, description in enumerate(descriptions)
    ]
    result = bank_dashboard_metrics(bank(rows))
    categories = chart(result, "debit_categories")["series"][0]["points"]
    values = {point["label"]: point["value"] for point in categories}
    assert values == {
        "food": 1,
        "housing": 2,
        "other": 7,
        "cash_withdrawal": 5,
        "transport": 6,
        "transfers": 7,
    }
    assert sum(values.values()) == 28
    assert chart(result, "daily_balances")["status"] == "unavailable"


def test_rankings_are_separate_positive_top_five_with_stable_ties():
    rows = [
        (
            "2026-01-02" if i % 2 else "2026-01-01",
            f"Synthetic {i}",
            "4" if i < 2 else "0",
            "5" if i else "0",
            "0",
            i + 6,
        )
        for i in range(8)
    ]
    result = bank_dashboard_metrics(bank(rows))
    inflows, outflows = result["largest_inflows"], result["largest_outflows"]
    assert len(inflows) == 5 and len(outflows) == 2
    assert [row["description"] for row in inflows] == [
        "Synthetic 2",
        "Synthetic 4",
        "Synthetic 6",
        "Synthetic 1",
        "Synthetic 3",
    ]
    assert outflows[0]["amount"] == 4
    assert set(inflows[0]) == {"amount", "unit", "date", "description", "source_refs"}
    assert inflows[0]["source_refs"][0]["field_paths"][-1] == "transactions[2].credit"


def test_large_fractional_amounts_survive_addition_and_negative_balances():
    amount = Decimal("123456789012345678901234567890.123456789")
    tiny = Decimal("0.000000000000000000001")
    with localcontext() as context:
        context.prec = 100
        closing = amount + tiny
    statement = bank(
        [
            ("2026-01-01", "A", "0", str(amount), str(amount), 6),
            ("2026-01-02", "B", "0", str(tiny), str(closing), 7),
        ],
        opening_balance=Decimal(0),
        closing_balance=closing,
    )
    result = bank_dashboard_metrics(statement)
    assert chart(result, "monthly_flows")["series"][0]["points"][0]["value"] == closing
    negative = bank(
        [
            ("2026-01-01", "Withdrawal", "10", "0", "-10", 6),
        ],
        opening_balance=Decimal(0),
        closing_balance=Decimal(-10),
    )
    assert metric(bank_dashboard_metrics(negative))["value"] == -10
    zero = bank(
        [
            ("2026-01-01", "Withdrawal", "100", "0", "0", 6),
        ],
        closing_balance=Decimal(0),
    )
    assert metric(bank_dashboard_metrics(zero))["value"] == 0


@pytest.mark.parametrize("layout", ["a", "b"])
def test_real_balance_layouts_keep_current_values_and_scale_once(layout):
    path = (
        ROOT
        / f"backend/tests/parsers/fixtures/synthetic_balance_sheet_layout_{layout}.csv"
    )
    parsed = parse_balance_sheet(
        path.read_bytes(), file_kind="csv", document_id=DOCUMENT
    )
    statement = ParsedBalanceSheet.model_validate(parsed.model_dump(mode="python"))
    result = balance_dashboard_metrics(statement)
    totals = chart(result, "reported_totals")["series"][0]["points"]
    assert totals[0]["value"] == (30_000_000 if layout == "a" else 2_000_000_000)
    components = chart(result, "balance_components")["series"][0]["points"]
    assert components[0]["value"] == (15_000_000 if layout == "a" else 800_000_000)
    with localcontext() as context:
        context.prec = 38
        assert metric(result)["value"] == (
            Decimal(40) / 180 if layout == "a" else Decimal("0.6")
        )
    assert metric(result)["unit"] == "ratio"
    assert result["largest_inflows"] == result["largest_outflows"] == []
    assert metric(result)["source_refs"][0]["document_id"] == str(DOCUMENT)
    assert "unit_scale" in totals[0]["source_refs"][0]["field_paths"]


@pytest.mark.parametrize(
    "change",
    [
        "currency",
        "scale",
        "equity",
        "zero_equity",
        "debt_amount",
        "unclassified",
        "unknown_row",
        "incomplete_total",
        "empty_liabilities",
    ],
)
def test_debt_coverage_and_missing_metadata_never_default_to_zero(change):
    statement = balance()
    if change == "currency":
        statement.currency = None
    elif change == "scale":
        statement.unit_scale = None
    elif change == "equity":
        statement.equity.total = None
    elif change == "zero_equity":
        statement.equity.total = Decimal(0)
    elif change == "debt_amount":
        statement.liabilities.non_current[0].value = None
    elif change == "unclassified":
        statement.liabilities.current[0].canonical_field = None
    elif change == "unknown_row":
        statement.unmapped = [
            {"reason": "unrecognized_financial_item", "source_row": 21}
        ]
    elif change == "incomplete_total":
        statement.liabilities.total = Decimal(121)
    else:
        statement.liabilities.current = []
        statement.liabilities.non_current = []
        statement.liabilities.total = Decimal(0)
    result = balance_dashboard_metrics(statement)
    assert metric(result)["value"] is None
    assert metric(result)["status"] == "unavailable" and metric(result)["reason"]
    if change in {"currency", "scale"}:
        assert all(item["series"] == [] for item in result["charts"])


def test_explicit_borrowing_zero_negative_equity_and_asset_loans_are_distinct():
    statement = balance()
    statement.equity.total = Decimal(-180)
    result = balance_dashboard_metrics(statement)
    with localcontext() as context:
        context.prec = 38
        assert metric(result)["value"] == Decimal(40) / -180
    assert any("negative" in warning for warning in result["warnings"])
    statement.liabilities.non_current[0].value = Decimal(0)
    statement.liabilities.total = Decimal(80)
    statement.assets.non_current[0].canonical_field = "other_non_current_assets"
    statement.assets.non_current[0].raw_label = "Loans and advances"
    assert metric(balance_dashboard_metrics(statement))["value"] == 0


def test_missing_breakdown_preserves_reported_totals_and_unknown_components():
    statement = balance()
    statement.assets.current[0].value = None
    result = balance_dashboard_metrics(statement)
    assert (
        chart(result, "reported_totals")["series"][0]["points"][0]["value"]
        == 30_000_000
    )
    components = chart(result, "balance_components")["series"][0]["points"]
    assert components[0]["value"] is None and components[0]["reason"]
    assert components[1]["value"] is None
    assert components[2]["value"] == 8_000_000


def test_same_day_branching_balance_paths_are_conservatively_unavailable():
    statement = bank(
        [
            ("2026-01-01", "A", "0", "10", "110", 6),
            ("2026-01-01", "B", "10", "0", "100", 7),
            ("2026-01-01", "C", "0", "20", "120", 8),
        ],
        closing_balance=Decimal(120),
    )
    result = bank_dashboard_metrics(statement)
    assert metric(result)["value"] is None
    assert chart(result, "daily_balances")["status"] == "unavailable"
    assert chart(result, "daily_flows")["series"][0]["points"][0]["value"] == 30


def test_large_statement_keeps_point_evidence_linear_and_does_not_mutate_input():
    first = date(2020, 1, 1)
    rows = [
        (
            (first + timedelta(days=i)).isoformat(),
            "Synthetic deposit",
            "0",
            "1",
            str(i + 1),
            i + 6,
        )
        for i in range(1000)
    ]
    statement = bank(
        rows,
        period_start=first,
        period_end=first + timedelta(days=999),
        opening_balance=Decimal(0),
        closing_balance=Decimal(1000),
    )
    before = statement.model_dump(mode="python")
    result = bank_dashboard_metrics(statement)
    assert statement.model_dump(mode="python") == before
    assert metric(result)["value"] == Decimal("500.5")
    points = chart(result, "daily_balances")["series"][0]["points"]
    assert len(points) == 1000
    assert sum(len(point["source_refs"][0]["field_paths"]) for point in points) == 2000


def test_both_supported_borrowing_types_enter_the_ratio_once():
    statement = balance()
    short = statement.liabilities.current[0].model_copy(
        update={
            "canonical_field": "short_term_borrowings",
            "value": Decimal(20),
            "source_row": 13,
        }
    )
    statement.liabilities.current.append(short)
    statement.liabilities.total = Decimal(140)
    result = balance_dashboard_metrics(statement)
    with localcontext() as context:
        context.prec = 38
        assert metric(result)["value"] == Decimal(60) / 180
    refs = metric(result)["source_refs"][0]
    assert {12, 13, 15} <= set(refs["source_rows"])
    assert "liabilities.current[1].value" in refs["field_paths"]


def test_all_missing_composition_points_mark_whole_charts_unavailable():
    statement = balance()
    statement.assets.total = statement.liabilities.total = statement.equity.total = None
    result = balance_dashboard_metrics(statement)
    assert all(item["status"] == "unavailable" for item in result["charts"])
    assert all(item["reason"] and item["series"] == [] for item in result["charts"])


def test_calendar_average_includes_leap_day_and_opening_days_without_transactions():
    statement = bank(
        [
            ("2028-02-28", "A", "0", "10", "110", 6),
            ("2028-02-29", "B", "20", "0", "90", 7),
        ],
        period_start="2028-02-28",
        period_end="2028-03-01",
    )
    with localcontext() as context:
        context.prec = 38
        assert metric(bank_dashboard_metrics(statement))["value"] == Decimal(290) / 3

    statement = bank(
        [
            ("2026-01-03", "A", "0", "10", "110", 6),
            ("2026-01-04", "B", "20", "0", "90", 7),
        ]
    )
    result = bank_dashboard_metrics(statement)
    assert metric(result)["value"] == 98
    first = chart(result, "daily_balances")["series"][0]["points"][0]
    assert (first["label"], first["value"]) == ("2026-01-01", 100)
    assert first["source_refs"][0]["field_paths"] == ["period_start", "opening_balance"]


def test_missing_or_invalid_optional_source_locations_do_not_fabricate_rows():
    statement = bank(
        source_locations={
            "period_start": None,
            "period_end": {"source_row": True},
            "opening_balance": {},
            "closing_balance": {},
        }
    )
    result = bank_dashboard_metrics(statement)
    assert metric(result)["value"] == 98
    assert metric(result)["source_refs"][0]["source_rows"] == [6, 7]
    assert "opening_balance" in metric(result)["source_refs"][0]["field_paths"]
    statement.source_locations["opening_balance"] = {"source_row": -8}
    invalid = bank_dashboard_metrics(statement)
    assert metric(invalid)["status"] == "unavailable"
    assert metric(invalid)["source_refs"] == []


def test_inventory_uses_the_supported_parser_classification():
    statement = balance()
    statement.assets.current[1].canonical_field = "inventory"
    result = balance_dashboard_metrics(statement)
    assert (
        chart(result, "balance_components")["series"][0]["points"][0]["value"]
        == 15_000_000
    )


def test_unbalanced_reported_totals_and_reference_rows_are_preserved():
    statement = balance()
    statement.equity.total = Decimal(179)
    statement.unmapped = [
        {"reason": reason, "source_row": 22}
        for reason in (
            "prior_period_value",
            "reported_subtotal",
            "unrecognized_note",
            "repeated_reported_value",
        )
    ]
    result = balance_dashboard_metrics(statement)
    totals = chart(result, "reported_totals")["series"][0]["points"]
    assert [point["value"] for point in totals] == [30_000_000, 12_000_000, 17_900_000]
    assert metric(result)["status"] == "available"
    assert result["warnings"] == [
        "Reported assets, liabilities and equity do not reconcile."
    ]
    assert (
        chart(result, "balance_components")["series"][0]["points"][0]["value"]
        == 15_000_000
    )
