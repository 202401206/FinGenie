"""Pure calculations for whole-document dashboard data.

Inputs are validated saved models. Calendar averages require verified running
balances and both statement boundaries. Recurring quotients use Decimal division
with at least 38 significant digits. No preference currency conversion is applied.

Category precedence follows CATEGORY_KEYWORDS from top to bottom. A keyword is a
whole word or phrase, so channel names such as UPI alone stay in other. These are
description labels and can misclassify a merchant's purpose.
"""

import re
from collections import defaultdict
from decimal import Decimal, localcontext
from typing import Any

from app.analysis.balance_sheet_kpis import calculate_balance_difference
from app.analysis.bank_kpis import (
    calculate_balance_reconciliation,
    calculate_net_cash_flow,
    calculate_total_credit,
    calculate_total_debit,
)
from app.db.parsed_models import ParsedBankStatement
from app.db.parsed_read_models import ParsedBalanceSheet

REFERENCE_REASONS = (
    "prior_period_value",
    "reported_subtotal",
    "unrecognized_note",
    "repeated_reported_value",
)
CATEGORY_KEYWORDS = (
    ("food", ("grocery", "groceries", "restaurant", "cafe", "swiggy", "zomato")),
    ("housing", ("rent", "hostel", "housing")),
    ("transport", ("bus", "metro", "taxi", "uber", "ola", "petrol", "fuel")),
    ("shopping", ("shopping", "amazon", "flipkart", "clothing")),
    ("utilities", ("electricity", "water bill", "broadband", "internet", "recharge")),
    ("education", ("tuition", "school", "college", "textbook")),
    ("entertainment", ("cinema", "movie", "netflix", "spotify")),
    ("cash_withdrawal", ("atm", "cash withdrawal")),
    ("transfers", ("transfer", "neft", "imps", "rtgs")),
)
ASSET_FIELDS = {
    "cash",
    "receivables",
    "inventory",
    "other_current_assets",
    "property_plant_equipment",
    "intangible_assets",
    "non_current_investments",
    "other_non_current_assets",
}
LIABILITY_FIELDS = {
    "trade_payables",
    "short_term_borrowings",
    "other_current_liabilities",
    "long_term_borrowings",
    "other_non_current_liabilities",
}
DEBT_FIELDS = {"short_term_borrowings", "long_term_borrowings"}


def _precision(amounts: list[Decimal]) -> int:
    # Include the exponent span so adding a tiny amount to a large one stays exact.
    if not amounts:
        return 38
    places = min(amount.as_tuple().exponent for amount in amounts)
    highest = max(amount.adjusted() for amount in amounts)
    return max(38, highest - places + len(str(len(amounts))) + 16)


def _refs(data: dict[str, Any], fields: list[tuple[int | None, str]]) -> list[dict]:
    if not fields:
        return []
    metadata = data["source_metadata"]
    return [
        {
            "document_id": str(metadata["document_id"]),
            "sheet_name": metadata["sheet_name"],
            "source_rows": sorted({row for row, _ in fields if row is not None}),
            "field_paths": list(dict.fromkeys(path for _, path in fields)),
        }
    ]


def _scalar_fields(data: dict, names: tuple[str, ...]) -> list[tuple[int | None, str]]:
    locations = data.get("source_locations", {})
    fields = []
    for name in names:
        location = locations.get(name)
        row = location.get("source_row") if isinstance(location, dict) else None
        fields.append((row if type(row) is int and row > 0 else None, name))
    return fields


def _transaction_fields(rows: list[tuple[int, Any]], names: tuple[str, ...]) -> list:
    return [
        (row.source_row, f"transactions[{index}].{name}")
        for index, row in rows
        for name in names
    ]


def _metric(
    key: str, unit: str, value: Decimal | None, refs: list, reason: str | None = None
) -> dict:
    return {
        "key": key,
        "unit": unit,
        "value": value,
        "status": "available" if value is not None else "unavailable",
        "reason": reason,
        "calculation_id": f"dashboard.{key}.v1",
        "source_refs": refs,
    }


def _point(
    label: str, value: Decimal | None, refs: list, reason: str | None = None
) -> dict:
    return {"label": label, "value": value, "reason": reason, "source_refs": refs}


def _chart(key: str, unit: str, series: list, reason: str | None = None) -> dict:
    has_points = any(
        point["value"] is not None for item in series for point in item["points"]
    )
    # A valid statement with no debits has an empty category series.
    available = has_points or (key == "debit_categories" and bool(series))
    return {
        "key": key,
        "unit": unit,
        "status": "available" if available else "unavailable",
        "reason": reason
        if available
        else reason or "No complete values are available.",
        "series": series if available else [],
    }


def _category(description: str) -> str:
    for category, words in CATEGORY_KEYWORDS:
        if any(
            re.search(r"\b" + re.escape(word) + r"\b", description, re.I)
            for word in words
        ):
            return category
    return "other"


def _flow_chart(statement: ParsedBankStatement, data: dict, monthly: bool) -> dict:
    key = "monthly_flows" if monthly else "daily_flows"
    unit = statement.currency or "unknown"
    if not statement.currency or not statement.transactions:
        return _chart(
            key, unit, [], "Confirmed currency and transactions are required."
        )
    groups = defaultdict(list)
    for index, row in enumerate(statement.transactions):
        label = row.date.isoformat()[:7] if monthly else row.date.isoformat()
        groups[label].append((index, row))
    series = []
    for name, function, fields in (
        ("credit", calculate_total_credit, ("date", "credit")),
        ("debit", calculate_total_debit, ("date", "debit")),
        ("net_flow", calculate_net_cash_flow, ("date", "credit", "debit")),
    ):
        points = []
        for label, rows in sorted(groups.items()):
            subset = dict(data, transactions=[data["transactions"][i] for i, _ in rows])
            metric = function(subset)
            refs = _refs(data, _transaction_fields(rows, fields))
            points.append(
                _point(
                    label,
                    metric["value"],
                    refs,
                    metric["reason"] or "Observed statement transactions only.",
                )
            )
        series.append(
            {"key": name, "label": name.replace("_", " ").title(), "points": points}
        )
    return _chart(
        key,
        unit,
        series,
        "Only observed transaction periods are shown. Omitted periods are gaps, "
        "not confirmed zero flows. Months may contain partial statement coverage.",
    )


def _largest(statement: ParsedBankStatement, data: dict, field: str) -> list:
    if not statement.currency:
        return []
    rows = [
        (i, row)
        for i, row in enumerate(statement.transactions)
        if getattr(row, field) > 0
    ]
    rows.sort(
        key=lambda pair: (-getattr(pair[1], field), pair[1].date, pair[1].source_row)
    )
    return [
        {
            "amount": getattr(row, field),
            "unit": statement.currency,
            "date": row.date,
            "description": row.description,
            "source_refs": _refs(
                data,
                _transaction_fields([(index, row)], ("date", "description", field)),
            ),
        }
        for index, row in rows[:5]
    ]


def _categories(statement: ParsedBankStatement, data: dict) -> dict:
    unit = statement.currency or "unknown"
    total = calculate_total_debit(data)
    if total["status"] != "available" or not statement.transactions:
        return _chart(
            "debit_categories",
            unit,
            [],
            "Confirmed currency and transactions are required.",
        )
    groups = defaultdict(list)
    for index, row in enumerate(statement.transactions):
        if row.debit > 0:
            groups[_category(row.description)].append((index, row))
    points = []
    for name, rows in sorted(groups.items()):
        value = sum((row.debit for _, row in rows), Decimal(0))
        refs = _refs(data, _transaction_fields(rows, ("description", "debit")))
        points.append(_point(name, value, refs))
    if sum((point["value"] for point in points), Decimal(0)) != total["value"]:
        return _chart(
            "debit_categories", unit, [], "Debit categories did not reconcile."
        )
    return _chart(
        "debit_categories",
        unit,
        [
            {
                "key": "debit",
                "label": "Observed debits",
                "points": points,
            }
        ],
        "Description keywords classify purpose approximately. UPI alone stays in other.",
    )


def _ordered_rows(statement: ParsedBankStatement) -> list | None:
    """Follow uniquely supported balance transitions within each calendar date."""
    rows = list(enumerate(statement.transactions))
    if len({row.source_row for _, row in rows}) != len(rows):
        return None
    days = defaultdict(list)
    for item in rows:
        days[item[1].date].append(item)
    balance = statement.opening_balance
    ordered = []
    for _, items in sorted(days.items()):
        starts = defaultdict(list)
        for item in items:
            row = item[1]
            starts[row.balance - row.credit + row.debit].append(item)
        for _ in items:
            candidates = starts.pop(balance, [])
            # Even a plausible source order is insufficient when two rows can follow.
            if len(candidates) != 1:
                return None
            item = candidates[0]
            ordered.append(item)
            balance = item[1].balance
    return ordered if balance == statement.closing_balance else None


def _daily_balances(statement: ParsedBankStatement, data: dict) -> tuple[dict, dict]:
    unit = statement.currency or "unknown"
    reason = None
    start, end = statement.period_start, statement.period_end
    if not statement.currency or start is None or end is None:
        reason = "Confirmed currency and both statement boundaries are required."
    elif statement.opening_balance is None or statement.closing_balance is None:
        reason = "Both reported opening and closing balances are required."
    elif not statement.transactions:
        reason = "No transactions establish the running-balance chronology."
    elif any(not start <= row.date <= end for row in statement.transactions):
        reason = "A transaction falls outside the reported period."
    elif any(
        row.get("reason")
        in {"insufficient_columns_for_transaction", "invalid_or_missing_date"}
        and not (
            re.search(r"\b(?:note|notice)\b", str(row.get("raw_label", "")), re.I)
            and not re.search(
                r"\d",
                str(row.get("raw_label", "")) + " " + str(row.get("raw_value", "")),
            )
        )
        for row in statement.unmapped
    ):
        # Supported parsers retain short nonfinancial notices under these reasons.
        # Ambiguous rows and notices containing numeric content remain unavailable.
        reason = "Unresolved transaction rows prevent complete balance coverage."
    else:
        reconciliation = calculate_balance_reconciliation(data)
        if reconciliation["status"] != "available" or reconciliation["value"] != 0:
            reason = "Reported balances and transaction flows do not reconcile."
    ordered = None if reason else _ordered_rows(statement)
    if reason is None and ordered is None:
        reason = "Running balances do not establish a unique within-day order."
    if reason:
        return (
            _metric("average_balance", unit, None, [], reason),
            _chart("daily_balances", unit, [], reason),
        )

    fields = _scalar_fields(
        data, ("period_start", "period_end", "opening_balance", "closing_balance")
    )
    refs = _refs(
        data,
        fields + _transaction_fields(ordered, ("date", "credit", "debit", "balance")),
    )
    days = defaultdict(list)
    for item in ordered:
        days[item[1].date].append(item)
    cursor, balance, weighted = start, statement.opening_balance, Decimal(0)
    points = []
    opening_fields = _scalar_fields(data, ("period_start", "opening_balance"))
    if start not in days:
        points.append(_point(start.isoformat(), balance, _refs(data, opening_fields)))
    for day, rows in sorted(days.items()):
        weighted += balance * (day - cursor).days
        balance = rows[-1][1].balance
        cursor = day
        # The EOD value is directly reported by the verified last row of the day.
        day_refs = _refs(data, _transaction_fields(rows[-1:], ("date", "balance")))
        points.append(_point(day.isoformat(), balance, day_refs))
    weighted += balance * ((end - cursor).days + 1)
    if points[-1]["label"] != end.isoformat():
        closing_fields = _scalar_fields(data, ("period_end", "closing_balance"))
        points.append(_point(end.isoformat(), balance, _refs(data, closing_fields)))
    average = weighted / Decimal((end - start).days + 1)
    return (
        _metric("average_balance", unit, average, refs),
        _chart(
            "daily_balances",
            unit,
            [
                {
                    "key": "balance",
                    "label": "End-of-day balance",
                    "points": points,
                }
            ],
            "Use a step line. A verified balance carries forward between points.",
        ),
    )


def bank_dashboard_metrics(statement: ParsedBankStatement) -> dict:
    """Additional bank metrics and charts for the entire saved statement."""
    data = statement.model_dump(mode="python")
    amounts = [
        amount
        for row in statement.transactions
        for amount in (row.credit, row.debit, row.balance)
    ]
    amounts += [
        value
        for value in (statement.opening_balance, statement.closing_balance)
        if value is not None
    ]
    with localcontext() as context:
        context.prec = _precision(amounts)
        average, balances = _daily_balances(statement, data)
        return {
            "metrics": [average],
            "charts": [
                _flow_chart(statement, data, False),
                _flow_chart(statement, data, True),
                balances,
                _categories(statement, data),
            ],
            "largest_inflows": _largest(statement, data, "credit"),
            "largest_outflows": _largest(statement, data, "debit"),
            "warnings": []
            if statement.currency
            else ["Statement currency is unknown."],
        }


def _complete_section(items: list, allowed: set[str], unresolved: bool) -> bool:
    return (
        bool(items)
        and not unresolved
        and all(
            item.value is not None and item.canonical_field in allowed for item in items
        )
    )


def _debt_to_equity(
    statement: ParsedBalanceSheet, data: dict, unresolved: bool
) -> dict:
    """Debt is classified short/long-term borrowings, with complete liability coverage."""
    items = statement.liabilities.current + statement.liabilities.non_current
    reason = None
    if not statement.currency or statement.unit_scale is None:
        reason = "Confirmed currency and unit scale are required."
    elif not _complete_section(items, LIABILITY_FIELDS, unresolved):
        reason = "Liability amounts or classifications are incomplete."
    elif (
        statement.liabilities.total is None
        or sum((item.value for item in items), Decimal(0))
        != statement.liabilities.total
    ):
        reason = "Liability leaves must cover the reported liability total."
    elif statement.equity.total is None or statement.equity.total == 0:
        reason = "Reported total equity must be present and nonzero."
    fields = _scalar_fields(data, ("unit_scale", "liabilities.total", "equity.total"))
    debt = Decimal(0)
    for section in ("current", "non_current"):
        for index, item in enumerate(getattr(statement.liabilities, section)):
            # All liability values establish coverage, including non-debt amounts.
            fields.append((item.source_row, f"liabilities.{section}[{index}].value"))
            if item.canonical_field in DEBT_FIELDS and item.value is not None:
                debt += item.value
    value = None if reason else debt / statement.equity.total
    return _metric("debt_to_equity", "ratio", value, _refs(data, fields), reason)


def _balance_composition(
    statement: ParsedBalanceSheet, data: dict, unresolved: bool
) -> list:
    unit = statement.currency or "unknown"
    if not statement.currency or statement.unit_scale is None:
        reason = "Confirmed currency and unit scale are required."
        return [
            _chart("reported_totals", unit, [], reason),
            _chart("balance_components", unit, [], reason),
        ]
    scale = Decimal(statement.unit_scale)
    totals = []
    for name in ("assets", "liabilities", "equity"):
        value = getattr(statement, name).total
        fields = _scalar_fields(data, ("unit_scale", f"{name}.total"))
        totals.append(
            _point(
                name,
                None if value is None else value * scale,
                _refs(data, fields),
                "Reported total is missing." if value is None else None,
            )
        )
    components = []
    for name, allowed in (("assets", ASSET_FIELDS), ("liabilities", LIABILITY_FIELDS)):
        section = getattr(statement, name)
        complete = all(
            _complete_section(getattr(section, part), allowed, unresolved)
            for part in ("current", "non_current")
        )
        leaves = section.current + section.non_current
        # Without equality, a complete-looking leaf list might omit an amount.
        covered = (
            complete
            and section.total is not None
            and sum((item.value for item in leaves), Decimal(0)) == section.total
        )
        for part in ("current", "non_current"):
            items = getattr(section, part)
            fields = _scalar_fields(data, ("unit_scale", f"{name}.total"))
            fields += [
                (item.source_row, f"{name}.{group}[{index}].value")
                for group in ("current", "non_current")
                for index, item in enumerate(getattr(section, group))
            ]
            value = (
                sum((item.value for item in items), Decimal(0)) * scale
                if covered
                else None
            )
            components.append(
                _point(
                    f"{name}_{part}",
                    value,
                    _refs(data, fields),
                    None
                    if covered
                    else "Classified leaves do not establish the complete reported section.",
                )
            )
    return [
        _chart(
            "reported_totals",
            unit,
            [{"key": "reported", "label": "Reported totals", "points": totals}],
        ),
        _chart(
            "balance_components",
            unit,
            [
                {
                    "key": "components",
                    "label": "Current and non-current",
                    "points": components,
                }
            ],
        ),
    ]


def balance_dashboard_metrics(statement: ParsedBalanceSheet) -> dict:
    """Snapshot totals, supported debt ratio and classified composition in base units."""
    data = statement.model_dump(mode="python")
    items = statement.assets.current + statement.assets.non_current
    items += statement.liabilities.current + statement.liabilities.non_current
    amounts = [item.value for item in items if item.value is not None]
    amounts += [
        section.total
        for section in (statement.assets, statement.liabilities, statement.equity)
        if section.total is not None
    ]
    unresolved = any(
        item.get("reason") not in REFERENCE_REASONS for item in statement.unmapped
    )
    with localcontext() as context:
        context.prec = _precision(amounts)
        warnings = []
        reconciliation = calculate_balance_difference(data)
        if reconciliation["value"] is not None and reconciliation["value"] != 0:
            warnings.append("Reported assets, liabilities and equity do not reconcile.")
        if statement.equity.total is not None and statement.equity.total < 0:
            warnings.append(
                "Reported equity is negative. Interpret debt-to-equity with care."
            )
        return {
            "metrics": [_debt_to_equity(statement, data, unresolved)],
            "charts": _balance_composition(statement, data, unresolved),
            "largest_inflows": [],
            "largest_outflows": [],
            "warnings": warnings,
        }
