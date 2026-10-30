"""Deterministic bank statement analytics and KPI calculation engine.

Ownership: Aarushi Shah (Bank Statement Analytics)
Track: Bank Analytics
Interface: Deterministic calculation of total credit, total debit, net cash flow,
and balance extraction adhering to team contracts in contracts/README.md.
"""

from decimal import Decimal, InvalidOperation
from typing import Any


def _to_decimal(val: Any) -> Decimal | None:
    """Safely converts an arbitrary numeric or string input to Decimal."""
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _get_document_metadata(data: dict[str, Any]) -> tuple[str, str | None]:
    """Extracts document_id and sheet_name from source_metadata."""
    metadata = data.get("source_metadata") or {}
    doc_id = str(metadata.get("document_id") or "")
    sheet_name = metadata.get("sheet_name")
    return doc_id, sheet_name


def calculate_total_credit(data: dict[str, Any]) -> Decimal:
    """Calculates sum of all incoming transactions (credit > 0).

    Args:
        data: Standardized bank statement dictionary.

    Returns:
        Exact Decimal sum of incoming credit amounts. Returns Decimal('0') if none.
    """
    total = Decimal("0")
    transactions = data.get("transactions") or []
    for tx in transactions:
        raw_credit = tx.get("credit")
        parsed = _to_decimal(raw_credit)
        if parsed is not None and parsed > Decimal("0"):
            total += parsed
    return total


def calculate_total_debit(data: dict[str, Any]) -> Decimal:
    """Calculates sum of all outgoing transactions (debit > 0).

    Args:
        data: Standardized bank statement dictionary.

    Returns:
        Exact Decimal sum of outgoing debit amounts. Returns Decimal('0') if none.
    """
    total = Decimal("0")
    transactions = data.get("transactions") or []
    for tx in transactions:
        raw_debit = tx.get("debit")
        parsed = _to_decimal(raw_debit)
        if parsed is not None and parsed > Decimal("0"):
            total += parsed
    return total


def calculate_net_cash_flow(data: dict[str, Any]) -> Decimal:
    """Calculates total credits minus total debits.

    Args:
        data: Standardized bank statement dictionary.

    Returns:
        Exact Decimal difference: total_credit - total_debit.
    """
    return calculate_total_credit(data) - calculate_total_debit(data)


def get_closing_balance(data: dict[str, Any]) -> Decimal | None:
    """Retrieves closing balance, or returns None if missing in the statement data.

    Args:
        data: Standardized bank statement dictionary.

    Returns:
        Decimal closing balance if present, otherwise None.
    """
    raw_closing = data.get("closing_balance")
    return _to_decimal(raw_closing)


def get_opening_balance(data: dict[str, Any]) -> Decimal | None:
    """Retrieves opening balance, or returns None if missing in the statement data.

    Args:
        data: Standardized bank statement dictionary.

    Returns:
        Decimal opening balance if present, otherwise None.
    """
    raw_opening = data.get("opening_balance")
    return _to_decimal(raw_opening)


# --- Traceability and Audit Source References ---


def get_total_credit_source_refs(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extracts 1-based source rows and field paths for credit transactions."""
    doc_id, sheet_name = _get_document_metadata(data)
    transactions = data.get("transactions") or []
    source_rows: list[int] = []
    field_paths: list[str] = []

    for idx, tx in enumerate(transactions):
        raw_credit = tx.get("credit")
        parsed = _to_decimal(raw_credit)
        if parsed is not None and parsed > Decimal("0"):
            row = tx.get("source_row")
            if isinstance(row, int) and row > 0:
                source_rows.append(row)
            field_paths.append(f"transactions[{idx}].credit")

    if not source_rows and not field_paths:
        return []

    return [
        {
            "document_id": doc_id,
            "sheet_name": sheet_name,
            "source_rows": sorted(source_rows),
            "field_paths": field_paths,
        }
    ]


def get_total_debit_source_refs(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extracts 1-based source rows and field paths for debit transactions."""
    doc_id, sheet_name = _get_document_metadata(data)
    transactions = data.get("transactions") or []
    source_rows: list[int] = []
    field_paths: list[str] = []

    for idx, tx in enumerate(transactions):
        raw_debit = tx.get("debit")
        parsed = _to_decimal(raw_debit)
        if parsed is not None and parsed > Decimal("0"):
            row = tx.get("source_row")
            if isinstance(row, int) and row > 0:
                source_rows.append(row)
            field_paths.append(f"transactions[{idx}].debit")

    if not source_rows and not field_paths:
        return []

    return [
        {
            "document_id": doc_id,
            "sheet_name": sheet_name,
            "source_rows": sorted(source_rows),
            "field_paths": field_paths,
        }
    ]


def get_net_cash_flow_source_refs(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extracts combined 1-based source rows and field paths for net cash flow."""
    doc_id, sheet_name = _get_document_metadata(data)
    transactions = data.get("transactions") or []
    source_rows: set[int] = set()
    field_paths: list[str] = []

    for idx, tx in enumerate(transactions):
        cr = _to_decimal(tx.get("credit"))
        dr = _to_decimal(tx.get("debit"))
        row = tx.get("source_row")
        row_valid = isinstance(row, int) and row > 0

        if cr is not None and cr > Decimal("0"):
            if row_valid and row is not None:
                source_rows.add(row)
            field_paths.append(f"transactions[{idx}].credit")

        if dr is not None and dr > Decimal("0"):
            if row_valid and row is not None:
                source_rows.add(row)
            field_paths.append(f"transactions[{idx}].debit")

    if not source_rows and not field_paths:
        return []

    return [
        {
            "document_id": doc_id,
            "sheet_name": sheet_name,
            "source_rows": sorted(list(source_rows)),
            "field_paths": field_paths,
        }
    ]


def get_closing_balance_source_refs(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extracts 1-based source row and field path for closing balance."""
    doc_id, sheet_name = _get_document_metadata(data)
    loc = (data.get("source_locations") or {}).get("closing_balance") or {}
    row = loc.get("source_row")
    source_rows = [row] if isinstance(row, int) and row > 0 else []

    return [
        {
            "document_id": doc_id,
            "sheet_name": sheet_name,
            "source_rows": source_rows,
            "field_paths": ["closing_balance"],
        }
    ]


# --- Full Analysis Generator (Contract Envelope) ---


def calculate_bank_analysis(
    data: dict[str, Any],
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Generates complete financial analysis response matching contracts/examples/financial-analysis.json.

    Args:
        data: Standardized bank statement dictionary.
        workspace_id: Optional workspace UUID string.

    Returns:
        Analysis response dictionary matching contract shape.
    """
    currency = data.get("currency")
    warnings: list[str] = []
    reliability = "valid"

    if not currency:
        reliability = "unreliable"
        warnings.append("Missing statement currency; monetary units unconfirmed.")
        currency = "unknown"

    transactions = data.get("transactions")
    if transactions is None:
        reliability = "insufficient_data"
        warnings.append("Statement contains no transaction data.")

    total_credit = calculate_total_credit(data)
    total_debit = calculate_total_debit(data)
    net_cash_flow = calculate_net_cash_flow(data)

    metrics = [
        {
            "key": "total_credit",
            "value": total_credit,
            "unit": currency,
            "status": "available",
            "reason": None,
            "calculation_id": "bank.total_credit.v1",
            "source_refs": get_total_credit_source_refs(data),
        },
        {
            "key": "total_debit",
            "value": total_debit,
            "unit": currency,
            "status": "available",
            "reason": None,
            "calculation_id": "bank.total_debit.v1",
            "source_refs": get_total_debit_source_refs(data),
        },
        {
            "key": "net_cash_flow",
            "value": net_cash_flow,
            "unit": currency,
            "status": "available",
            "reason": None,
            "calculation_id": "bank.net_cash_flow.v1",
            "source_refs": get_net_cash_flow_source_refs(data),
        },
    ]

    closing = get_closing_balance(data)
    if closing is not None:
        metrics.append(
            {
                "key": "closing_balance",
                "value": closing,
                "unit": currency,
                "status": "available",
                "reason": None,
                "calculation_id": "bank.closing_balance.v1",
                "source_refs": get_closing_balance_source_refs(data),
            }
        )

    return {
        "workspace_id": workspace_id or "00000000-0000-0000-0000-000000000000",
        "document_type": "bank_statement",
        "currency": currency,
        "reliability": reliability,
        "metrics": metrics,
        "warnings": warnings,
    }
