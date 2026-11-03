"""Deterministic balance sheet analytics and KPI calculation engine.

Ownership: Aarushi Shah (Balance Sheet Analytics)
Track: Balance Sheet Analytics
Interface: Deterministic calculation of working capital, current ratio,
balance difference reconciliation, and full analysis envelope matching
contracts/examples/balance-sheet-analysis.json.
"""

from decimal import Decimal, InvalidOperation
from typing import Any

CALCULATION_ID_WORKING_CAPITAL = "balance_sheet.working_capital.v1"
CALCULATION_ID_CURRENT_RATIO = "balance_sheet.current_ratio.v1"
CALCULATION_ID_BALANCE_DIFFERENCE = "balance_sheet.balance_difference.v1"

STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"

RELIABILITY_VALID = "valid"
RELIABILITY_UNRELIABLE = "unreliable"
RELIABILITY_INSUFFICIENT_DATA = "insufficient_data"


def _to_decimal(val: Any) -> Decimal | None:
    """Safely converts an arbitrary numeric or string input to Decimal.

    Sanitizes string inputs by stripping whitespace and removing commas
    (e.g., '1,500.00' or ' 5,000 '). Rejects booleans and non-finite values.
    """
    if val is None or val == "":
        return None
    if isinstance(val, bool):
        return None
    try:
        if isinstance(val, str):
            cleaned = val.replace(",", "").strip()
            if cleaned == "":
                return None
            return Decimal(cleaned)
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _is_valid_source_row(val: Any) -> bool:
    """Check if val is a valid positive integer representing a 1-based source row."""
    return isinstance(val, int) and not isinstance(val, bool) and val >= 1


def _get_document_metadata(data: dict[str, Any]) -> tuple[str, str | None]:
    """Extracts document_id and sheet_name from source_metadata."""
    if not isinstance(data, dict):
        return "", None
    metadata = data.get("source_metadata")
    if not isinstance(metadata, dict):
        return "", None
    doc_id = str(metadata.get("document_id") or "")
    sheet_name = metadata.get("sheet_name")
    return doc_id, sheet_name if isinstance(sheet_name, str) else None


def _extract_line_items_total(
    items: Any,
    field_prefix: str,
) -> tuple[Decimal, list[int], list[str]]:
    """Sums values from a list of line-item dicts and gathers 1-based source rows and field paths."""
    total = Decimal("0")
    source_rows: list[int] = []
    field_paths: list[str] = []

    if not isinstance(items, list):
        return total, source_rows, field_paths

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        val = _to_decimal(item.get("value"))
        if val is not None:
            total += val
            row = item.get("source_row")
            if _is_valid_source_row(row):
                source_rows.append(row)
            field_paths.append(f"{field_prefix}[{idx}].value")

    return total, source_rows, field_paths


def calculate_working_capital(statement_data: dict[str, Any]) -> dict[str, Any]:
    """Calculates Working Capital: (Current Assets - Current Liabilities) * unit_scale.

    Formula:
        working_capital = (sum(current_assets) - sum(current_liabilities)) * unit_scale

    Rules:
        - unit_scale comes from statement_data["unit_scale"] (1 = units, 1000 = thousands, 100000 = lakhs, 10000000 = crores).
        - Value is converted to base currency (e.g., INR 7,000,000).
        - calculation_id: "balance_sheet.working_capital.v1".
        - Traceability: collects source_rows from unit_scale and all contributing line items.
    """
    doc_id, sheet_name = _get_document_metadata(statement_data)
    currency = (
        statement_data.get("currency") if isinstance(statement_data, dict) else None
    )

    if not isinstance(statement_data, dict):
        return {
            "key": "working_capital",
            "value": None,
            "unit": "unknown",
            "status": STATUS_UNAVAILABLE,
            "reason": "Missing or invalid statement data dictionary.",
            "calculation_id": CALCULATION_ID_WORKING_CAPITAL,
            "source_refs": [],
        }

    scale_val = _to_decimal(statement_data.get("unit_scale"))
    if scale_val is None:
        return {
            "key": "working_capital",
            "value": None,
            "unit": currency or "unknown",
            "status": STATUS_UNAVAILABLE,
            "reason": "Missing required 'unit_scale' in balance sheet data.",
            "calculation_id": CALCULATION_ID_WORKING_CAPITAL,
            "source_refs": [],
        }

    assets = statement_data.get("assets")
    liabilities = statement_data.get("liabilities")

    if not isinstance(assets, dict) or not isinstance(liabilities, dict):
        return {
            "key": "working_capital",
            "value": None,
            "unit": currency or "unknown",
            "status": STATUS_UNAVAILABLE,
            "reason": "Missing required 'assets' or 'liabilities' sections in balance sheet.",
            "calculation_id": CALCULATION_ID_WORKING_CAPITAL,
            "source_refs": [],
        }

    curr_assets_total, ca_rows, ca_paths = _extract_line_items_total(
        assets.get("current"), "assets.current"
    )
    curr_liab_total, cl_rows, cl_paths = _extract_line_items_total(
        liabilities.get("current"), "liabilities.current"
    )

    source_locations = statement_data.get("source_locations") or {}
    scale_loc = source_locations.get("unit_scale") or {}
    scale_row = scale_loc.get("source_row")

    source_rows: list[int] = []
    if _is_valid_source_row(scale_row):
        source_rows.append(scale_row)
    source_rows.extend(ca_rows)
    source_rows.extend(cl_rows)

    field_paths = ["unit_scale"] + ca_paths + cl_paths

    working_capital_base = (curr_assets_total - curr_liab_total) * scale_val

    source_refs = [
        {
            "document_id": doc_id,
            "sheet_name": sheet_name,
            "source_rows": source_rows,
            "field_paths": field_paths,
        }
    ]

    return {
        "key": "working_capital",
        "value": working_capital_base,
        "unit": currency or "unknown",
        "status": STATUS_AVAILABLE,
        "reason": None,
        "calculation_id": CALCULATION_ID_WORKING_CAPITAL,
        "source_refs": source_refs,
    }


def calculate_current_ratio(statement_data: dict[str, Any]) -> dict[str, Any]:
    """Calculates Current Ratio: Current Assets / Current Liabilities in reported units.

    Formula:
        current_ratio = sum(current_assets) / sum(current_liabilities)

    Rules:
        - Do NOT apply unit_scale to the ratio itself. unit is "ratio".
        - Zero-Division Guard: If Current Liabilities == 0, return status="unavailable" with descriptive reason.
        - calculation_id: "balance_sheet.current_ratio.v1".
        - Traceability: collects source_rows from all contributing line items.
    """
    doc_id, sheet_name = _get_document_metadata(statement_data)

    if not isinstance(statement_data, dict):
        return {
            "key": "current_ratio",
            "value": None,
            "unit": "ratio",
            "status": STATUS_UNAVAILABLE,
            "reason": "Missing or invalid statement data dictionary.",
            "calculation_id": CALCULATION_ID_CURRENT_RATIO,
            "source_refs": [],
        }

    assets = statement_data.get("assets")
    liabilities = statement_data.get("liabilities")

    if not isinstance(assets, dict) or not isinstance(liabilities, dict):
        return {
            "key": "current_ratio",
            "value": None,
            "unit": "ratio",
            "status": STATUS_UNAVAILABLE,
            "reason": "Missing required 'assets' or 'liabilities' sections in balance sheet.",
            "calculation_id": CALCULATION_ID_CURRENT_RATIO,
            "source_refs": [],
        }

    curr_assets_total, ca_rows, ca_paths = _extract_line_items_total(
        assets.get("current"), "assets.current"
    )
    curr_liab_total, cl_rows, cl_paths = _extract_line_items_total(
        liabilities.get("current"), "liabilities.current"
    )

    source_rows = ca_rows + cl_rows
    field_paths = ca_paths + cl_paths

    source_refs = (
        [
            {
                "document_id": doc_id,
                "sheet_name": sheet_name,
                "source_rows": source_rows,
                "field_paths": field_paths,
            }
        ]
        if source_rows or field_paths
        else []
    )

    if curr_liab_total == Decimal("0"):
        return {
            "key": "current_ratio",
            "value": None,
            "unit": "ratio",
            "status": STATUS_UNAVAILABLE,
            "reason": "Current liabilities are zero; cannot calculate current ratio (division by zero).",
            "calculation_id": CALCULATION_ID_CURRENT_RATIO,
            "source_refs": source_refs,
        }

    ratio = curr_assets_total / curr_liab_total

    return {
        "key": "current_ratio",
        "value": ratio,
        "unit": "ratio",
        "status": STATUS_AVAILABLE,
        "reason": None,
        "calculation_id": CALCULATION_ID_CURRENT_RATIO,
        "source_refs": source_refs,
    }


def calculate_balance_difference(statement_data: dict[str, Any]) -> dict[str, Any]:
    """Calculates balance reconciliation discrepancy: Total Assets - (Total Liabilities + Total Equity).

    Formula:
        difference = Total Assets - (Total Liabilities + Total Equity)

    Rules:
        - A difference of Decimal("0") indicates a perfectly balanced statement.
        - calculation_id: "balance_sheet.balance_difference.v1".
        - Traceability: points to source_rows of unit_scale, assets.total, liabilities.total, and equity.total.
    """
    doc_id, sheet_name = _get_document_metadata(statement_data)
    currency = (
        statement_data.get("currency") if isinstance(statement_data, dict) else None
    )

    if not isinstance(statement_data, dict):
        return {
            "key": "balance_difference",
            "value": None,
            "unit": "unknown",
            "status": STATUS_UNAVAILABLE,
            "reason": "Missing or invalid statement data dictionary.",
            "calculation_id": CALCULATION_ID_BALANCE_DIFFERENCE,
            "source_refs": [],
        }

    assets = statement_data.get("assets")
    liabilities = statement_data.get("liabilities")
    equity = statement_data.get("equity")

    if (
        not isinstance(assets, dict)
        or not isinstance(liabilities, dict)
        or not isinstance(equity, dict)
    ):
        return {
            "key": "balance_difference",
            "value": None,
            "unit": currency or "unknown",
            "status": STATUS_UNAVAILABLE,
            "reason": "Missing assets, liabilities, or equity sections for reconciliation.",
            "calculation_id": CALCULATION_ID_BALANCE_DIFFERENCE,
            "source_refs": [],
        }

    total_assets = _to_decimal(assets.get("total"))
    total_liab = _to_decimal(liabilities.get("total"))
    total_equity = _to_decimal(equity.get("total"))

    if total_assets is None or total_liab is None or total_equity is None:
        return {
            "key": "balance_difference",
            "value": None,
            "unit": currency or "unknown",
            "status": STATUS_UNAVAILABLE,
            "reason": "Missing 'total' field in assets, liabilities, or equity.",
            "calculation_id": CALCULATION_ID_BALANCE_DIFFERENCE,
            "source_refs": [],
        }

    diff = total_assets - (total_liab + total_equity)

    source_locations = statement_data.get("source_locations") or {}
    source_rows: list[int] = []
    field_paths: list[str] = []

    # Traceability sequence matching contract fixture: unit_scale, assets.total, liabilities.total, equity.total
    scale_row = (source_locations.get("unit_scale") or {}).get("source_row")
    if _is_valid_source_row(scale_row):
        source_rows.append(scale_row)
    field_paths.append("unit_scale")

    assets_row = (source_locations.get("assets.total") or {}).get("source_row")
    if _is_valid_source_row(assets_row):
        source_rows.append(assets_row)
    field_paths.append("assets.total")

    liab_row = (source_locations.get("liabilities.total") or {}).get("source_row")
    if _is_valid_source_row(liab_row):
        source_rows.append(liab_row)
    field_paths.append("liabilities.total")

    eq_row = (source_locations.get("equity.total") or {}).get("source_row")
    if _is_valid_source_row(eq_row):
        source_rows.append(eq_row)
    field_paths.append("equity.total")

    source_refs = [
        {
            "document_id": doc_id,
            "sheet_name": sheet_name,
            "source_rows": source_rows,
            "field_paths": field_paths,
        }
    ]

    return {
        "key": "balance_difference",
        "value": diff,
        "unit": currency or "unknown",
        "status": STATUS_AVAILABLE,
        "reason": None,
        "calculation_id": CALCULATION_ID_BALANCE_DIFFERENCE,
        "source_refs": source_refs,
    }


def analyze_balance_sheet(
    statement_data: dict[str, Any],
    workspace_id: str | None = None,
    *,
    include_current_ratio: bool = False,
) -> dict[str, Any]:
    """Generates the full financial analysis envelope matching contracts/examples/balance-sheet-analysis.json.

    Args:
        statement_data: Standardized balance sheet dictionary.
        workspace_id: Optional workspace UUID string.
        include_current_ratio: If True, appends current_ratio metric to metrics.

    Returns:
        Complete envelope dictionary with workspace_id, document_type, currency,
        reliability, metrics, and warnings.
    """
    if not isinstance(statement_data, dict):
        statement_data = {}

    currency = statement_data.get("currency")
    warnings: list[str] = []
    reliability = RELIABILITY_VALID

    if not currency:
        reliability = RELIABILITY_UNRELIABLE
        warnings.append("Missing statement currency; monetary units unconfirmed.")
        currency = "unknown"

    scale_val = _to_decimal(statement_data.get("unit_scale"))
    if scale_val is None:
        reliability = RELIABILITY_INSUFFICIENT_DATA
        warnings.append("Missing unit_scale in balance sheet data.")

    wc_metric = calculate_working_capital(statement_data)
    diff_metric = calculate_balance_difference(statement_data)

    metrics = [wc_metric, diff_metric]

    if include_current_ratio:
        ratio_metric = calculate_current_ratio(statement_data)
        metrics.append(ratio_metric)

    # Reconciliation and reliability check
    if diff_metric["status"] != STATUS_AVAILABLE:
        reliability = RELIABILITY_INSUFFICIENT_DATA
        if diff_metric["reason"]:
            warnings.append(diff_metric["reason"])
    elif diff_metric["value"] != Decimal("0"):
        reliability = RELIABILITY_UNRELIABLE
        warnings.append(
            f"Balance sheet reconciliation failed: Assets != Liabilities + Equity (discrepancy: {diff_metric['value']})."
        )

    return {
        "workspace_id": workspace_id or "00000000-0000-0000-0000-000000000000",
        "document_type": "balance_sheet",
        "currency": currency,
        "reliability": reliability,
        "metrics": metrics,
        "warnings": warnings,
    }


def serialize_analysis_result(analysis: dict[str, Any]) -> dict[str, Any]:
    """Serializes Decimal values in an analysis result dict to JSON-serializable primitives (int/float).

    Converts integral Decimals (e.g. Decimal('7000000')) to int and fractional
    Decimals (e.g. Decimal('1.875')) to float.
    """
    if not isinstance(analysis, dict):
        return analysis

    serialized = dict(analysis)
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
