"""Bank statement KPI calculations and balance reconciliation.

Pure Python module implementing deterministic financial metrics for bank statements
using Decimal arithmetic, strict source traceability, and safe missing-data handling.
No database, HTTP, Supabase, environment-secret, or LLM dependencies.
"""

import math
from decimal import Decimal, InvalidOperation
from typing import Any

CALCULATION_ID_TOTAL_CREDIT = "bank.total_credit.v1"
CALCULATION_ID_TOTAL_DEBIT = "bank.total_debit.v1"
CALCULATION_ID_NET_CASH_FLOW = "bank.net_cash_flow.v1"
CALCULATION_ID_BALANCE_RECONCILIATION = "bank.balance_reconciliation.v1"

STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"

RELIABILITY_VALID = "valid"
RELIABILITY_UNRELIABLE = "unreliable"
RELIABILITY_INSUFFICIENT_DATA = "insufficient_data"


def _to_decimal(val: Any) -> Decimal:
    """Convert an int, str, float, or Decimal to Decimal safely.

    Raises InvalidOperation if the value is NaN, infinite, boolean, or cannot be parsed.
    """
    if isinstance(val, bool):
        raise InvalidOperation("Boolean value cannot be converted to money Decimal.")

    if isinstance(val, Decimal):
        d = val
    elif isinstance(val, (int, str)):
        d = Decimal(str(val))
    elif isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            raise InvalidOperation("NaN or Infinity float is not allowed.")
        d = Decimal(str(val))
    else:
        raise InvalidOperation(
            f"Unsupported type {type(val)!r} for Decimal conversion."
        )

    if d.is_nan() or d.is_infinite():
        raise InvalidOperation("NaN or Infinity Decimal is not allowed.")

    return d


def _is_valid_source_row(val: Any) -> bool:
    """Check if val is a valid positive integer representing a 1-based source row."""
    return isinstance(val, int) and not isinstance(val, bool) and val >= 1


def _get_source_metadata(
    statement_data: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Extract document_id and sheet_name from statement source_metadata."""
    if not isinstance(statement_data, dict):
        return None, None
    metadata = statement_data.get("source_metadata")
    if isinstance(metadata, dict):
        return metadata.get("document_id"), metadata.get("sheet_name")
    return None, None


def _build_source_ref(
    document_id: str | None,
    sheet_name: str | None,
    source_rows: list[int],
    field_paths: list[str],
) -> list[dict[str, Any]]:
    """Build a list containing a single source_ref contract dictionary."""
    return [
        {
            "document_id": document_id,
            "sheet_name": sheet_name,
            "source_rows": source_rows,
            "field_paths": field_paths,
        }
    ]


def calculate_total_credit(statement_data: dict[str, Any]) -> dict[str, Any]:
    """Calculate total credit by summing non-negative credit fields from transactions.

    Traceability:
        - Only transactions with credit > 0 contribute to source_rows and field_paths.
        - Preserves document_id and sheet_name from source_metadata.
        - Validates source_row as a positive integer (>= 1) when present.

    Safety:
        - Never silently replaces missing, null, or invalid credit with zero.
        - Rejects NaN, Infinity, negative values, and non-numeric inputs.
        - Returns status='unavailable' with a descriptive reason on invalid data.
    """
    currency = (
        statement_data.get("currency") if isinstance(statement_data, dict) else None
    )
    doc_id, sheet_name = (
        _get_source_metadata(statement_data)
        if isinstance(statement_data, dict)
        else (None, None)
    )

    if not isinstance(statement_data, dict) or "transactions" not in statement_data:
        return {
            "key": "total_credit",
            "value": None,
            "unit": currency,
            "status": STATUS_UNAVAILABLE,
            "reason": "Missing required 'transactions' in statement data.",
            "calculation_id": CALCULATION_ID_TOTAL_CREDIT,
            "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
        }

    transactions = statement_data.get("transactions")
    if transactions is None or not isinstance(transactions, list):
        return {
            "key": "total_credit",
            "value": None,
            "unit": currency,
            "status": STATUS_UNAVAILABLE,
            "reason": "'transactions' must be a non-null list.",
            "calculation_id": CALCULATION_ID_TOTAL_CREDIT,
            "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
        }

    total_credit = Decimal("0")
    source_rows: list[int] = []
    field_paths: list[str] = []

    for idx, tx in enumerate(transactions):
        if not isinstance(tx, dict):
            return {
                "key": "total_credit",
                "value": None,
                "unit": currency,
                "status": STATUS_UNAVAILABLE,
                "reason": f"Transaction at index {idx} must be a dictionary.",
                "calculation_id": CALCULATION_ID_TOTAL_CREDIT,
                "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
            }

        if "source_row" in tx and tx["source_row"] is not None:
            sr = tx["source_row"]
            if not _is_valid_source_row(sr):
                return {
                    "key": "total_credit",
                    "value": None,
                    "unit": currency,
                    "status": STATUS_UNAVAILABLE,
                    "reason": (
                        f"Transaction at index {idx} has invalid source_row: {sr!r} "
                        "(must be a positive integer >= 1)."
                    ),
                    "calculation_id": CALCULATION_ID_TOTAL_CREDIT,
                    "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
                }

        if "credit" not in tx or tx["credit"] is None:
            source_row_info = (
                f" (source_row: {tx.get('source_row')})"
                if tx.get("source_row") is not None
                else ""
            )
            return {
                "key": "total_credit",
                "value": None,
                "unit": currency,
                "status": STATUS_UNAVAILABLE,
                "reason": f"Transaction at index {idx}{source_row_info} is missing required 'credit' field.",
                "calculation_id": CALCULATION_ID_TOTAL_CREDIT,
                "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
            }

        try:
            credit_amount = _to_decimal(tx["credit"])
        except (InvalidOperation, TypeError):
            return {
                "key": "total_credit",
                "value": None,
                "unit": currency,
                "status": STATUS_UNAVAILABLE,
                "reason": f"Transaction at index {idx} has invalid non-numeric credit: {tx['credit']!r}.",
                "calculation_id": CALCULATION_ID_TOTAL_CREDIT,
                "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
            }

        if credit_amount < Decimal("0"):
            return {
                "key": "total_credit",
                "value": None,
                "unit": currency,
                "status": STATUS_UNAVAILABLE,
                "reason": f"Transaction at index {idx} has negative credit magnitude: {tx['credit']}.",
                "calculation_id": CALCULATION_ID_TOTAL_CREDIT,
                "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
            }

        if credit_amount > Decimal("0"):
            total_credit += credit_amount
            field_paths.append(f"transactions[{idx}].credit")
            if tx.get("source_row") is not None:
                source_rows.append(tx["source_row"])

    return {
        "key": "total_credit",
        "value": total_credit,
        "unit": currency,
        "status": STATUS_AVAILABLE,
        "reason": None,
        "calculation_id": CALCULATION_ID_TOTAL_CREDIT,
        "source_refs": _build_source_ref(doc_id, sheet_name, source_rows, field_paths),
    }


def calculate_total_debit(statement_data: dict[str, Any]) -> dict[str, Any]:
    """Calculate total debit by summing non-negative debit fields from transactions.

    Traceability:
        - Only transactions with debit > 0 contribute to source_rows and field_paths.
        - Preserves document_id and sheet_name from source_metadata.
        - Validates source_row as a positive integer (>= 1) when present.

    Safety:
        - Never silently replaces missing, null, or invalid debit with zero.
        - Rejects NaN, Infinity, negative values, and non-numeric inputs.
        - Returns status='unavailable' with a descriptive reason on invalid data.
    """
    currency = (
        statement_data.get("currency") if isinstance(statement_data, dict) else None
    )
    doc_id, sheet_name = (
        _get_source_metadata(statement_data)
        if isinstance(statement_data, dict)
        else (None, None)
    )

    if not isinstance(statement_data, dict) or "transactions" not in statement_data:
        return {
            "key": "total_debit",
            "value": None,
            "unit": currency,
            "status": STATUS_UNAVAILABLE,
            "reason": "Missing required 'transactions' in statement data.",
            "calculation_id": CALCULATION_ID_TOTAL_DEBIT,
            "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
        }

    transactions = statement_data.get("transactions")
    if transactions is None or not isinstance(transactions, list):
        return {
            "key": "total_debit",
            "value": None,
            "unit": currency,
            "status": STATUS_UNAVAILABLE,
            "reason": "'transactions' must be a non-null list.",
            "calculation_id": CALCULATION_ID_TOTAL_DEBIT,
            "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
        }

    total_debit = Decimal("0")
    source_rows: list[int] = []
    field_paths: list[str] = []

    for idx, tx in enumerate(transactions):
        if not isinstance(tx, dict):
            return {
                "key": "total_debit",
                "value": None,
                "unit": currency,
                "status": STATUS_UNAVAILABLE,
                "reason": f"Transaction at index {idx} must be a dictionary.",
                "calculation_id": CALCULATION_ID_TOTAL_DEBIT,
                "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
            }

        if "source_row" in tx and tx["source_row"] is not None:
            sr = tx["source_row"]
            if not _is_valid_source_row(sr):
                return {
                    "key": "total_debit",
                    "value": None,
                    "unit": currency,
                    "status": STATUS_UNAVAILABLE,
                    "reason": (
                        f"Transaction at index {idx} has invalid source_row: {sr!r} "
                        "(must be a positive integer >= 1)."
                    ),
                    "calculation_id": CALCULATION_ID_TOTAL_DEBIT,
                    "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
                }

        if "debit" not in tx or tx["debit"] is None:
            source_row_info = (
                f" (source_row: {tx.get('source_row')})"
                if tx.get("source_row") is not None
                else ""
            )
            return {
                "key": "total_debit",
                "value": None,
                "unit": currency,
                "status": STATUS_UNAVAILABLE,
                "reason": f"Transaction at index {idx}{source_row_info} is missing required 'debit' field.",
                "calculation_id": CALCULATION_ID_TOTAL_DEBIT,
                "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
            }

        try:
            debit_amount = _to_decimal(tx["debit"])
        except (InvalidOperation, TypeError):
            return {
                "key": "total_debit",
                "value": None,
                "unit": currency,
                "status": STATUS_UNAVAILABLE,
                "reason": f"Transaction at index {idx} has invalid non-numeric debit: {tx['debit']!r}.",
                "calculation_id": CALCULATION_ID_TOTAL_DEBIT,
                "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
            }

        if debit_amount < Decimal("0"):
            return {
                "key": "total_debit",
                "value": None,
                "unit": currency,
                "status": STATUS_UNAVAILABLE,
                "reason": f"Transaction at index {idx} has negative debit magnitude: {tx['debit']}.",
                "calculation_id": CALCULATION_ID_TOTAL_DEBIT,
                "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
            }

        if debit_amount > Decimal("0"):
            total_debit += debit_amount
            field_paths.append(f"transactions[{idx}].debit")
            if tx.get("source_row") is not None:
                source_rows.append(tx["source_row"])

    return {
        "key": "total_debit",
        "value": total_debit,
        "unit": currency,
        "status": STATUS_AVAILABLE,
        "reason": None,
        "calculation_id": CALCULATION_ID_TOTAL_DEBIT,
        "source_refs": _build_source_ref(doc_id, sheet_name, source_rows, field_paths),
    }


def calculate_net_cash_flow(
    statement_data: dict[str, Any],
    total_credit_metric: dict[str, Any] | None = None,
    total_debit_metric: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate net cash flow = total_credit - total_debit.

    Traceability:
        - Combines source_rows from both contributing credit and debit transactions.
        - Preserves field_paths from credit followed by debit.

    Safety:
        - If either credit or debit is unavailable, net cash flow is marked unavailable.
    """
    currency = (
        statement_data.get("currency") if isinstance(statement_data, dict) else None
    )
    doc_id, sheet_name = (
        _get_source_metadata(statement_data)
        if isinstance(statement_data, dict)
        else (None, None)
    )

    if total_credit_metric is None:
        total_credit_metric = calculate_total_credit(statement_data)
    if total_debit_metric is None:
        total_debit_metric = calculate_total_debit(statement_data)

    if (
        total_credit_metric.get("status") != STATUS_AVAILABLE
        or total_debit_metric.get("status") != STATUS_AVAILABLE
    ):
        reasons = []
        if total_credit_metric.get("reason"):
            reasons.append(f"total_credit: {total_credit_metric['reason']}")
        if total_debit_metric.get("reason"):
            reasons.append(f"total_debit: {total_debit_metric['reason']}")
        reason_msg = "Net cash flow unavailable: " + (
            "; ".join(reasons) if reasons else "underlying metrics unavailable."
        )
        return {
            "key": "net_cash_flow",
            "value": None,
            "unit": currency,
            "status": STATUS_UNAVAILABLE,
            "reason": reason_msg,
            "calculation_id": CALCULATION_ID_NET_CASH_FLOW,
            "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
        }

    credit_val: Decimal = total_credit_metric["value"]
    debit_val: Decimal = total_debit_metric["value"]
    net_val = credit_val - debit_val

    # Aggregate contributing source rows (preserving unique sorted order)
    credit_refs = total_credit_metric.get("source_refs", [{}])[0]
    debit_refs = total_debit_metric.get("source_refs", [{}])[0]

    credit_rows = credit_refs.get("source_rows", [])
    debit_rows = debit_refs.get("source_rows", [])
    combined_rows = sorted(list(dict.fromkeys(credit_rows + debit_rows)))

    credit_paths = credit_refs.get("field_paths", [])
    debit_paths = debit_refs.get("field_paths", [])
    combined_paths = list(dict.fromkeys(credit_paths + debit_paths))

    return {
        "key": "net_cash_flow",
        "value": net_val,
        "unit": currency,
        "status": STATUS_AVAILABLE,
        "reason": None,
        "calculation_id": CALCULATION_ID_NET_CASH_FLOW,
        "source_refs": _build_source_ref(
            doc_id, sheet_name, combined_rows, combined_paths
        ),
    }


def calculate_balance_reconciliation(
    statement_data: dict[str, Any],
    total_credit_metric: dict[str, Any] | None = None,
    total_debit_metric: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate balance reconciliation and verify equation:
    opening_balance + total_credit - total_debit = closing_balance.

    Value:
        Discrepancy difference = (opening_balance + total_credit - total_debit) - closing_balance.
        A difference of Decimal("0") indicates perfect balance.

    Traceability:
        - Points to opening_balance source_row, contributing transactions, and closing_balance source_row.
        - field_paths: ["opening_balance", ...transactions..., "closing_balance"].
        - Validates source_locations and nested values safely against unexpected types.

    Safety:
        - Never silently replaces missing opening_balance or closing_balance with zero.
        - Rejects NaN, Infinity, and non-numeric balances.
        - Returns status='unavailable' when required balances are absent or invalid.
    """
    currency = (
        statement_data.get("currency") if isinstance(statement_data, dict) else None
    )
    doc_id, sheet_name = (
        _get_source_metadata(statement_data)
        if isinstance(statement_data, dict)
        else (None, None)
    )

    if not isinstance(statement_data, dict):
        return {
            "key": "balance_reconciliation",
            "value": None,
            "unit": currency,
            "status": STATUS_UNAVAILABLE,
            "reason": "Invalid statement data type (expected dict).",
            "calculation_id": CALCULATION_ID_BALANCE_RECONCILIATION,
            "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
        }

    # Validate opening_balance and closing_balance existence
    missing_balances = []
    if (
        "opening_balance" not in statement_data
        or statement_data["opening_balance"] is None
    ):
        missing_balances.append("opening_balance")
    if (
        "closing_balance" not in statement_data
        or statement_data["closing_balance"] is None
    ):
        missing_balances.append("closing_balance")

    if missing_balances:
        return {
            "key": "balance_reconciliation",
            "value": None,
            "unit": currency,
            "status": STATUS_UNAVAILABLE,
            "reason": f"Missing required balance field(s): {', '.join(missing_balances)}.",
            "calculation_id": CALCULATION_ID_BALANCE_RECONCILIATION,
            "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
        }

    try:
        opening_balance = _to_decimal(statement_data["opening_balance"])
    except (InvalidOperation, TypeError):
        return {
            "key": "balance_reconciliation",
            "value": None,
            "unit": currency,
            "status": STATUS_UNAVAILABLE,
            "reason": f"Invalid non-numeric 'opening_balance': {statement_data['opening_balance']!r}.",
            "calculation_id": CALCULATION_ID_BALANCE_RECONCILIATION,
            "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
        }

    try:
        closing_balance = _to_decimal(statement_data["closing_balance"])
    except (InvalidOperation, TypeError):
        return {
            "key": "balance_reconciliation",
            "value": None,
            "unit": currency,
            "status": STATUS_UNAVAILABLE,
            "reason": f"Invalid non-numeric 'closing_balance': {statement_data['closing_balance']!r}.",
            "calculation_id": CALCULATION_ID_BALANCE_RECONCILIATION,
            "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
        }

    if total_credit_metric is None:
        total_credit_metric = calculate_total_credit(statement_data)
    if total_debit_metric is None:
        total_debit_metric = calculate_total_debit(statement_data)

    if (
        total_credit_metric.get("status") != STATUS_AVAILABLE
        or total_debit_metric.get("status") != STATUS_AVAILABLE
    ):
        return {
            "key": "balance_reconciliation",
            "value": None,
            "unit": currency,
            "status": STATUS_UNAVAILABLE,
            "reason": "Balance reconciliation unavailable because total_credit or total_debit is unavailable.",
            "calculation_id": CALCULATION_ID_BALANCE_RECONCILIATION,
            "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
        }

    total_credit: Decimal = total_credit_metric["value"]
    total_debit: Decimal = total_debit_metric["value"]

    expected_closing = opening_balance + total_credit - total_debit
    difference = expected_closing - closing_balance

    # Robust extraction and validation of source_locations and nested row references
    opening_row: int | None = None
    closing_row: int | None = None

    if (
        "source_locations" in statement_data
        and statement_data["source_locations"] is not None
    ):
        source_locations = statement_data["source_locations"]
        if not isinstance(source_locations, dict):
            return {
                "key": "balance_reconciliation",
                "value": None,
                "unit": currency,
                "status": STATUS_UNAVAILABLE,
                "reason": (
                    f"Expected 'source_locations' to be a dict, got {type(source_locations).__name__}."
                ),
                "calculation_id": CALCULATION_ID_BALANCE_RECONCILIATION,
                "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
            }

        opening_loc = source_locations.get("opening_balance")
        if opening_loc is not None:
            if not isinstance(opening_loc, dict):
                return {
                    "key": "balance_reconciliation",
                    "value": None,
                    "unit": currency,
                    "status": STATUS_UNAVAILABLE,
                    "reason": (
                        "Expected 'source_locations.opening_balance' to be a dict, "
                        f"got {type(opening_loc).__name__}."
                    ),
                    "calculation_id": CALCULATION_ID_BALANCE_RECONCILIATION,
                    "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
                }
            if "source_row" in opening_loc and opening_loc["source_row"] is not None:
                sr = opening_loc["source_row"]
                if not _is_valid_source_row(sr):
                    return {
                        "key": "balance_reconciliation",
                        "value": None,
                        "unit": currency,
                        "status": STATUS_UNAVAILABLE,
                        "reason": (
                            f"Invalid 'source_row' in source_locations.opening_balance: {sr!r} "
                            "(must be a positive integer >= 1)."
                        ),
                        "calculation_id": CALCULATION_ID_BALANCE_RECONCILIATION,
                        "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
                    }
                opening_row = sr

        closing_loc = source_locations.get("closing_balance")
        if closing_loc is not None:
            if not isinstance(closing_loc, dict):
                return {
                    "key": "balance_reconciliation",
                    "value": None,
                    "unit": currency,
                    "status": STATUS_UNAVAILABLE,
                    "reason": (
                        "Expected 'source_locations.closing_balance' to be a dict, "
                        f"got {type(closing_loc).__name__}."
                    ),
                    "calculation_id": CALCULATION_ID_BALANCE_RECONCILIATION,
                    "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
                }
            if "source_row" in closing_loc and closing_loc["source_row"] is not None:
                sr = closing_loc["source_row"]
                if not _is_valid_source_row(sr):
                    return {
                        "key": "balance_reconciliation",
                        "value": None,
                        "unit": currency,
                        "status": STATUS_UNAVAILABLE,
                        "reason": (
                            f"Invalid 'source_row' in source_locations.closing_balance: {sr!r} "
                            "(must be a positive integer >= 1)."
                        ),
                        "calculation_id": CALCULATION_ID_BALANCE_RECONCILIATION,
                        "source_refs": _build_source_ref(doc_id, sheet_name, [], []),
                    }
                closing_row = sr

    credit_refs = total_credit_metric.get("source_refs", [{}])[0]
    debit_refs = total_debit_metric.get("source_refs", [{}])[0]

    credit_rows = credit_refs.get("source_rows", [])
    debit_rows = debit_refs.get("source_rows", [])

    reconciliation_rows: list[int] = []
    if opening_row is not None:
        reconciliation_rows.append(opening_row)
    reconciliation_rows.extend(credit_rows)
    reconciliation_rows.extend(debit_rows)
    if closing_row is not None:
        reconciliation_rows.append(closing_row)
    reconciliation_rows = sorted(list(dict.fromkeys(reconciliation_rows)))

    credit_paths = credit_refs.get("field_paths", [])
    debit_paths = debit_refs.get("field_paths", [])
    reconciliation_paths = (
        ["opening_balance"]
        + list(dict.fromkeys(credit_paths + debit_paths))
        + ["closing_balance"]
    )

    reason = None
    if difference != Decimal("0"):
        reason = (
            f"Balance reconciliation mismatch: opening_balance ({opening_balance}) + "
            f"total_credit ({total_credit}) - total_debit ({total_debit}) = "
            f"{expected_closing}, but closing_balance is {closing_balance} "
            f"(difference: {difference})."
        )

    return {
        "key": "balance_reconciliation",
        "value": difference,
        "unit": currency,
        "status": STATUS_AVAILABLE,
        "reason": reason,
        "calculation_id": CALCULATION_ID_BALANCE_RECONCILIATION,
        "source_refs": _build_source_ref(
            doc_id, sheet_name, reconciliation_rows, reconciliation_paths
        ),
    }


def calculate_bank_kpis(
    statement_data: dict[str, Any],
    *,
    include_reconciliation_metric: bool = False,
) -> list[dict[str, Any]]:
    """Compute bank statement metrics (total credit, total debit, net cash flow, and optional reconciliation)."""
    credit_metric = calculate_total_credit(statement_data)
    debit_metric = calculate_total_debit(statement_data)
    net_metric = calculate_net_cash_flow(statement_data, credit_metric, debit_metric)

    metrics = [credit_metric, debit_metric, net_metric]
    if include_reconciliation_metric:
        recon_metric = calculate_balance_reconciliation(
            statement_data, credit_metric, debit_metric
        )
        metrics.append(recon_metric)

    return metrics


def analyze_bank_statement(
    statement_data: dict[str, Any],
    workspace_id: str | None = None,
    *,
    include_reconciliation_metric: bool = False,
) -> dict[str, Any]:
    """Execute complete bank statement analysis following the financial-analysis envelope contract.

    Envelope structure:
        - workspace_id: Provided UUID or workspace identifier.
        - document_type: "bank_statement".
        - currency: Statement currency code (e.g. "INR").
        - reliability: "valid", "unreliable", or "insufficient_data".
        - metrics: List of calculated metric objects.
        - warnings: List of warning strings if reconciliation fails or data is incomplete.

    Reconciliation & Reliability Policy:
        Balance reconciliation (opening_balance + total_credit - total_debit = closing_balance)
        is intentionally calculated in all cases to determine the document's overall reliability
        status ("valid", "unreliable", or "insufficient_data") and generate warnings,
        even when include_reconciliation_metric=False.

        When include_reconciliation_metric is False (default), the metrics array contains only
        the primary metrics [total_credit, total_debit, net_cash_flow] matching the contract
        fixture in contracts/examples/financial-analysis.json.
        When True, the reconciliation metric is also appended to the metrics array.
    """
    credit_metric = calculate_total_credit(statement_data)
    debit_metric = calculate_total_debit(statement_data)
    net_metric = calculate_net_cash_flow(statement_data, credit_metric, debit_metric)
    recon_metric = calculate_balance_reconciliation(
        statement_data, credit_metric, debit_metric
    )

    warnings: list[str] = []

    # Assess reliability and warnings
    if (
        credit_metric.get("status") != STATUS_AVAILABLE
        or debit_metric.get("status") != STATUS_AVAILABLE
        or net_metric.get("status") != STATUS_AVAILABLE
        or recon_metric.get("status") != STATUS_AVAILABLE
    ):
        reliability = RELIABILITY_INSUFFICIENT_DATA
        for m in (credit_metric, debit_metric, net_metric, recon_metric):
            if m.get("status") != STATUS_AVAILABLE and m.get("reason"):
                warnings.append(m["reason"])
    elif recon_metric.get("value") != Decimal("0"):
        reliability = RELIABILITY_UNRELIABLE
        if recon_metric.get("reason"):
            warnings.append(recon_metric["reason"])
    else:
        reliability = RELIABILITY_VALID

    metrics = [credit_metric, debit_metric, net_metric]
    if include_reconciliation_metric:
        metrics.append(recon_metric)

    resolved_workspace_id = (
        workspace_id
        if workspace_id is not None
        else (
            statement_data.get("workspace_id")
            if isinstance(statement_data, dict)
            else None
        )
    )

    currency = (
        statement_data.get("currency") if isinstance(statement_data, dict) else None
    )

    return {
        "workspace_id": resolved_workspace_id,
        "document_type": "bank_statement",
        "currency": currency,
        "reliability": reliability,
        "metrics": metrics,
        "warnings": warnings,
    }


def serialize_analysis_result(analysis_result: dict[str, Any]) -> dict[str, Any]:
    """Convert Decimal metric values in an analysis result dict to JSON numbers.

    Converts integral Decimals to int (e.g. Decimal("5000") -> 5000) and
    fractional Decimals to float (e.g. Decimal("50.25") -> 50.25) to preserve
    the agreed numeric JSON contract when served by FastAPI or Pydantic.
    """
    if not isinstance(analysis_result, dict):
        return analysis_result

    serialized = dict(analysis_result)
    metrics = serialized.get("metrics")
    if isinstance(metrics, list):
        serialized_metrics = []
        for m in metrics:
            if isinstance(m, dict):
                m_copy = dict(m)
                val = m_copy.get("value")
                if isinstance(val, Decimal):
                    m_copy["value"] = int(val) if val % 1 == 0 else float(val)
                serialized_metrics.append(m_copy)
            else:
                serialized_metrics.append(m)
        serialized["metrics"] = serialized_metrics

    return serialized
