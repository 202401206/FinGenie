"""Pure balance sheet CSV parser supporting Layout A and Layout B using standard library csv and Decimal arithmetic."""

import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from app.parsers.errors import (
    InvalidStatementError,
    ResourceLimitError,
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

MAX_SOURCE_BYTES = 5 * 1024 * 1024  # 5 MiB
MAX_ROWS = 20_000
MAX_COLUMNS = 50
MAX_CELL_CHARS = 131_072  # 128 KiB per CSV cell

# Supported currencies and scales
SUPPORTED_CURRENCIES = {"INR", "USD"}

SCALE_MAPPINGS = {
    "units": 1,
    "actuals": 1,
    "1": 1,
    "thousands": 1_000,
    "in thousands": 1_000,
    "1000": 1_000,
    "lakhs": 100_000,
    "lakh": 100_000,
    "in lakhs": 100_000,
    "100000": 100_000,
    "millions": 1_000_000,
    "million": 1_000_000,
    "in millions": 1_000_000,
    "1000000": 1_000_000,
    "crores": 10_000_000,
    "crore": 10_000_000,
    "in crores": 10_000_000,
    "10000000": 10_000_000,
}

# Canonical line item aliases
CANONICAL_LINE_ITEMS: dict[str, dict[str, list[str]]] = {
    "assets": {
        "cash": [
            "cash",
            "cash and cash equivalents",
            "cash & cash equivalents",
            "cash & bank",
            "bank balances",
            "cash and bank balances",
            "cash on hand",
            "cash at bank",
        ],
        "receivables": [
            "trade receivables",
            "receivables",
            "accounts receivable",
            "debtors",
            "sundry debtors",
        ],
        "inventory": [
            "inventories",
            "inventory",
            "stock",
            "stock-in-trade",
        ],
        "other_current_assets": [
            "other current assets",
            "prepaid expenses",
            "short-term loans and advances",
        ],
        "property_plant_equipment": [
            "property, plant and equipment",
            "property plant and equipment",
            "equipment",
            "fixed assets",
            "tangible assets",
            "ppe",
        ],
        "intangible_assets": [
            "intangible assets",
            "goodwill",
        ],
        "non_current_investments": [
            "non-current investments",
            "long-term investments",
            "investments",
        ],
        "other_non_current_assets": [
            "other non-current assets",
            "long-term loans and advances",
        ],
    },
    "liabilities": {
        "trade_payables": [
            "trade payables",
            "payables",
            "accounts payable",
            "creditors",
            "sundry creditors",
        ],
        "short_term_borrowings": [
            "short-term borrowings",
            "short term borrowings",
            "short-term debt",
            "short term loans",
        ],
        "other_current_liabilities": [
            "other current liabilities",
            "accrued expenses",
            "provisions",
            "short-term provisions",
        ],
        "long_term_borrowings": [
            "long-term borrowings",
            "long term borrowings",
            "long-term loan",
            "long-term debt",
            "long term debt",
            "bonds payable",
        ],
        "other_non_current_liabilities": [
            "other non-current liabilities",
            "long-term provisions",
            "deferred tax liabilities",
        ],
    },
}

EQUITY_LINE_ITEMS = {
    "share_capital": [
        "share capital",
        "common stock",
        "equity share capital",
        "contributed capital",
    ],
    "retained_earnings": [
        "retained earnings",
        "reserves and surplus",
        "surplus",
        "accumulated deficit",
        "accumulated losses",
    ],
}

REPORTED_TOTAL_LABELS = {
    "assets.total": [
        "total assets",
        "total current & non-current assets",
        "total current and non-current assets",
    ],
    "liabilities.total": [
        "total liabilities",
        "total current & non-current liabilities",
        "total current and non-current liabilities",
    ],
    "equity.total": [
        "total equity",
        "total shareholders' funds",
        "total stockholders' equity",
        "total equity and reserves",
    ],
}

REPORTED_SUBTOTAL_LABELS = [
    "total current assets",
    "total non-current assets",
    "total current liabilities",
    "total non-current liabilities",
    "total equity and liabilities",
    "total liabilities and equity",
]

SECTION_HEADINGS = {
    "assets_current": [
        "current assets",
        "i. current assets",
        "assets - current",
    ],
    "assets_non_current": [
        "non-current assets",
        "non current assets",
        "fixed assets",
        "non-current",
        "ii. non-current assets",
    ],
    "assets_root": [
        "assets",
        "i. assets",
    ],
    "liabilities_current": [
        "current liabilities",
        "liabilities - current",
        "i. current liabilities",
    ],
    "liabilities_non_current": [
        "non-current liabilities",
        "non current liabilities",
        "long-term liabilities",
        "long term liabilities",
        "long-term borrowings",
        "long term borrowings",
        "ii. non-current liabilities",
    ],
    "liabilities_root": [
        "liabilities",
        "equity and liabilities",
        "equity & liabilities",
    ],
    "equity_root": [
        "equity",
        "shareholders' funds",
        "shareholder's funds",
        "shareholders funds",
        "stockholders' equity",
        "capital and reserves",
    ],
}


def _clean_str(val: str | None) -> str:
    return val.strip() if val else ""


def _parse_decimal(raw: str, *, source_row: int, field_name: str) -> Decimal:
    """Parse monetary Decimal in reported units, allowing negative values."""
    cleaned = _clean_str(raw)
    if not cleaned:
        raise InvalidStatementError(
            f"Missing required numeric value for {field_name} at row {source_row}"
        )

    # Reject formulas
    if cleaned.startswith("="):
        raise InvalidStatementError(f"Formula found in cell at row {source_row}")

    # Remove commas
    cleaned = cleaned.replace(",", "")

    # Handle parenthesized negative representation: (100.00) -> -100.00
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1].strip()}"

    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise InvalidStatementError(
            f"Invalid numeric value for {field_name} at row {source_row}"
        ) from exc

    if not amount.is_finite():
        raise InvalidStatementError(
            f"Non-finite numeric value for {field_name} at row {source_row}"
        )

    return amount


def _parse_date(raw: str, *, source_row: int) -> date:
    """Parse reporting date supporting ISO (YYYY-MM-DD) and delimited formats."""
    cleaned = _clean_str(raw)
    if not cleaned:
        raise InvalidStatementError(
            f"Missing required reporting date at row {source_row}"
        )

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    raise InvalidStatementError(
        f"Invalid reporting date format at row {source_row}; expected YYYY-MM-DD or DD/MM/YYYY"
    )


def _try_parse_header_period(cell: str) -> tuple[str, date | int] | None:
    """Attempt to parse date (ISO/delimited) or 4-digit year from a header cell."""
    cleaned = _clean_str(cell)
    if not cleaned:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return ("date", datetime.strptime(cleaned, fmt).date())
        except ValueError:
            continue

    if re.fullmatch(r"\d{4}", cleaned):
        try:
            return ("year", int(cleaned))
        except ValueError:
            pass

    return None


def _try_parse_header_date(cell: str) -> date | None:
    """Attempt to parse date or 4-digit year from a column header cell."""
    res = _try_parse_header_period(cell)
    if res is None:
        return None
    kind, val = res
    if kind == "date":
        assert isinstance(val, date)
        return val
    elif kind == "year":
        assert isinstance(val, int)
        return date(val, 1, 1)
    return None


def _extract_key_values(
    record: list[str],
) -> list[tuple[str, str, int]]:
    """Extract (key, value, col_idx) pairs from a preamble row."""
    kv_list: list[tuple[str, str, int]] = []
    i = 0
    while i < len(record):
        cell = record[i].strip()
        if not cell:
            i += 1
            continue
        if ":" in cell:
            key, val = cell.split(":", 1)
            k = key.strip().lower()
            v = val.strip()
            if k:
                kv_list.append((k, v, i))
            i += 1
        else:
            if i + 1 < len(record) and record[i + 1].strip():
                k = cell.strip().lower()
                v = record[i + 1].strip()
                kv_list.append((k, v, i))
                i += 2
            else:
                i += 1
    return kv_list


def _match_layout_a_header(row: list[str]) -> dict[str, int] | None:
    """Check if row matches Layout A table header (Particulars, Amount).

    Returns a dict with 'particulars_col' and 'amount_col' (0-based indices)
    if the row matches Layout A, or None if it is not a Layout A header.
    Raises InvalidStatementError if header contains conflicting or unexpected columns.
    """
    particulars_aliases = {
        "particulars",
        "description",
        "items",
        "line items",
        "account",
    }
    amount_aliases = {
        "amount",
        "balance",
        "value",
        "total",
    }

    clean_cells = [_clean_str(c) for c in row]
    particulars_cols: list[int] = []
    amount_cols: list[int] = []
    unexpected_cols: list[tuple[int, str]] = []

    for idx, c in enumerate(clean_cells):
        if not c:
            continue
        c_lower = c.lower()
        if c_lower in particulars_aliases:
            particulars_cols.append(idx)
        elif c_lower in amount_aliases:
            amount_cols.append(idx)
        else:
            unexpected_cols.append((idx, c))

    if not particulars_cols or not amount_cols:
        return None

    if len(particulars_cols) > 1:
        raise InvalidStatementError("Duplicate particulars column in table header")
    if len(amount_cols) > 1:
        raise InvalidStatementError("Duplicate amount column in table header")
    if unexpected_cols:
        first_extra = unexpected_cols[0][1]
        raise InvalidStatementError(
            f"Unexpected populated column in table header: '{first_extra}'"
        )

    return {
        "particulars_col": particulars_cols[0],
        "amount_col": amount_cols[0],
    }


def _match_layout_b_header(row: list[str]) -> dict[str, Any] | None:
    """Check if row matches Layout B header: Particulars, [Note No], <date1>, <date2>."""
    clean_cells = [_clean_str(c) for c in row]
    non_empty = [c for c in clean_cells if c]
    if len(non_empty) < 3:
        return None

    norm_cells = [c.lower() for c in clean_cells]
    particulars_aliases = {
        "particulars",
        "description",
        "items",
        "line items",
        "account",
    }

    particulars_cols = [
        idx for idx, c in enumerate(norm_cells) if c in particulars_aliases
    ]
    if len(particulars_cols) == 0:
        return None
    if len(particulars_cols) > 1:
        raise InvalidStatementError("Duplicate particulars column in table header")
    particulars_col = particulars_cols[0]

    # Optional Note column
    note_aliases = {"note no", "note no.", "note", "notes", "schedule", "ref"}
    note_col = None

    parsed_dates: list[tuple[date, int, str]] = []
    seen_dates: dict[date, str] = {}
    seen_years: dict[int, str] = {}
    unexpected_cols: list[tuple[int, str]] = []

    for idx in range(particulars_col + 1, len(clean_cells)):
        cell_raw = clean_cells[idx]
        cell_lower = norm_cells[idx]
        if not cell_raw:
            continue

        if cell_lower in note_aliases:
            if note_col is not None:
                raise InvalidStatementError("Duplicate note column in table header")
            note_col = idx
            continue

        period_info = _try_parse_header_period(cell_raw)
        if period_info is not None:
            kind, period_val = period_info
            if kind == "date":
                d = period_val
                assert isinstance(d, date)
                if d in seen_dates:
                    raise InvalidStatementError(
                        f"Duplicate period column '{cell_raw}' in table header"
                    )
                if d.year in seen_years:
                    raise InvalidStatementError(
                        f"Ambiguous overlapping period column '{cell_raw}' in table header"
                    )
                seen_dates[d] = cell_raw
                parsed_dates.append((d, idx, cell_raw))
            elif kind == "year":
                y = period_val
                assert isinstance(y, int)
                if y in seen_years:
                    raise InvalidStatementError(
                        f"Duplicate period column '{cell_raw}' in table header"
                    )
                if any(d.year == y for d in seen_dates):
                    raise InvalidStatementError(
                        f"Ambiguous overlapping period column '{cell_raw}' in table header"
                    )
                seen_years[y] = cell_raw
                parsed_dates.append((date(y, 1, 1), idx, cell_raw))
            continue

        unexpected_cols.append((idx, cell_raw))

    if len(parsed_dates) < 2:
        return None

    # Check for any unexpected non-empty columns before particulars_col
    for idx in range(0, particulars_col):
        if clean_cells[idx]:
            unexpected_cols.append((idx, clean_cells[idx]))

    if unexpected_cols:
        first_extra = unexpected_cols[0][1]
        raise InvalidStatementError(
            f"Unexpected populated column in table header: '{first_extra}'"
        )

    return {
        "particulars_col": particulars_col,
        "note_col": note_col,
        "dated_cols": parsed_dates,
    }


class MetadataAccumulator:
    """Accumulates and resolves balance sheet preamble metadata according to agreed layout contracts."""

    def __init__(self) -> None:
        self.company: str | None = None
        self.company_row: int | None = None
        self.reporting_date: date | None = None
        self.reporting_date_row: int | None = None
        self.currencies: list[tuple[str, str, int]] = []
        self.scales: list[tuple[str, str, int]] = []
        self.other_preamble: list[tuple[str, str, int]] = []

    def record_company(self, v: str, row_idx: int) -> None:
        v_clean = v.strip()
        if not v_clean:
            return
        if self.company is None:
            self.company = v_clean
            self.company_row = row_idx
        elif self.company != v_clean:
            raise InvalidStatementError(
                f"Contradictory company declarations in preamble ('{self.company}' vs '{v_clean}') at row {row_idx}"
            )

    def record_reporting_date(self, v: str, row_idx: int) -> None:
        v_clean = v.strip()
        if not v_clean:
            return
        parsed_d = _parse_date(v_clean, source_row=row_idx)
        if self.reporting_date is None:
            self.reporting_date = parsed_d
            self.reporting_date_row = row_idx
        elif self.reporting_date != parsed_d:
            raise InvalidStatementError(
                f"Contradictory reporting date declarations in preamble ('{self.reporting_date}' vs '{parsed_d}') at row {row_idx}"
            )

    def record_currency(self, k: str, v: str, row_idx: int) -> None:
        self.currencies.append((k, v, row_idx))

    def record_unit_scale(self, k: str, v: str, row_idx: int) -> None:
        self.scales.append((k, v, row_idx))

    def record_note(self, k: str, v: str, row_idx: int) -> None:
        self.other_preamble.append((k, v, row_idx))

    def resolve(
        self,
    ) -> tuple[
        str | None,
        date | None,
        str | None,
        int | None,
        dict[str, SourceLocation],
        list[UnmappedItem],
    ]:
        source_locations: dict[str, SourceLocation] = {}
        unmapped: list[UnmappedItem] = []

        if self.company is not None and self.company_row is not None:
            source_locations["company"] = SourceLocation(source_row=self.company_row)

        if self.reporting_date is not None and self.reporting_date_row is not None:
            source_locations["reporting_date"] = SourceLocation(
                source_row=self.reporting_date_row
            )

        # Resolve currencies
        resolved_curr: str | None = None
        curr_row: int | None = None
        has_ambiguous_curr = False

        for k, v, r in self.currencies:
            norm = v.strip().upper()
            if norm in ("INR", "INDIAN RUPEES", "₹"):
                code = "INR"
            elif norm in ("USD", "US DOLLARS"):
                code = "USD"
            elif norm in ("RS.", "RS", "$"):
                code = "AMBIGUOUS"
                has_ambiguous_curr = True
                unmapped.append(
                    UnmappedItem(
                        source_row=r,
                        raw_label=k,
                        raw_value=v,
                        reason="ambiguous_currency",
                    )
                )
                continue
            else:
                raise InvalidStatementError(
                    f"Unsupported balance sheet currency '{v}' at row {r}"
                )

            if resolved_curr is None:
                resolved_curr = code
                curr_row = r
            elif resolved_curr != code:
                raise InvalidStatementError(
                    f"Contradictory currency declarations in preamble ('{resolved_curr}' vs '{code}') at row {r}"
                )

        if has_ambiguous_curr:
            final_currency = None
        else:
            final_currency = resolved_curr
            if final_currency is not None and curr_row is not None:
                source_locations["currency"] = SourceLocation(source_row=curr_row)

        # Resolve unit scale
        resolved_scale: int | None = None
        scale_row: int | None = None
        has_ambiguous_scale = False

        for k, v, r in self.scales:
            scale_key = v.strip().lower()
            if scale_key in SCALE_MAPPINGS:
                multiplier = SCALE_MAPPINGS[scale_key]
                if resolved_scale is None:
                    resolved_scale = multiplier
                    scale_row = r
                elif resolved_scale != multiplier:
                    raise InvalidStatementError(
                        f"Contradictory unit scale declarations in preamble ({resolved_scale} vs {multiplier}) at row {r}"
                    )
            else:
                has_ambiguous_scale = True
                unmapped.append(
                    UnmappedItem(
                        source_row=r,
                        raw_label=k,
                        raw_value=v,
                        reason="ambiguous_unit_scale",
                    )
                )

        if has_ambiguous_scale:
            final_scale = None
        else:
            final_scale = resolved_scale
            if final_scale is not None and scale_row is not None:
                source_locations["unit_scale"] = SourceLocation(source_row=scale_row)

        for k, v, r in self.other_preamble:
            unmapped.append(
                UnmappedItem(
                    source_row=r,
                    raw_label=k,
                    raw_value=v,
                    reason="unrecognized_note",
                )
            )

        return (
            self.company,
            self.reporting_date,
            final_currency,
            final_scale,
            source_locations,
            unmapped,
        )


class ScalarTracker:
    """Tracks scalar total and equity fields, validating against duplicate conflicts."""

    def __init__(
        self,
        source_locations: dict[str, SourceLocation],
        unmapped: list[UnmappedItem],
    ) -> None:
        self.seen: dict[str, tuple[Decimal | None, int, str]] = {}
        self.source_locations = source_locations
        self.unmapped = unmapped

    def record_scalar(
        self,
        key: str,
        value: Decimal | None,
        source_row: int,
        raw_label: str,
        raw_value_str: str,
    ) -> Decimal | None:
        if key not in self.seen:
            self.seen[key] = (value, source_row, raw_label)
            self.source_locations[key] = SourceLocation(source_row=source_row)
            return value

        prev_val, prev_row, prev_label = self.seen[key]
        if prev_val != value:
            raise InvalidStatementError(
                f"Conflicting value for duplicate scalar field '{key}' at row {source_row}"
            )

        # Same normalized value: accept deterministically, preserve repeated source row in unmapped
        self.unmapped.append(
            UnmappedItem(
                source_row=source_row,
                raw_label=raw_label,
                raw_value=raw_value_str,
                reason="repeated_reported_value",
            )
        )
        return prev_val


class TableStateMachine:
    """Processes table body rows into line items, totals, and unmapped entries."""

    def __init__(
        self,
        scalar_tracker: ScalarTracker,
        unmapped: list[UnmappedItem],
        source_locations: dict[str, SourceLocation],
    ) -> None:
        self.scalar_tracker = scalar_tracker
        self.unmapped = unmapped
        self.source_locations = source_locations

        self.current_section: str = "assets"
        self.current_subsection: str | None = None

        self.assets_current: list[LineItem] = []
        self.assets_non_current: list[LineItem] = []
        self.liabilities_current: list[LineItem] = []
        self.liabilities_non_current: list[LineItem] = []

        self.assets_total: Decimal | None = None
        self.liabilities_total: Decimal | None = None
        self.equity_total: Decimal | None = None
        self.share_capital: Decimal | None = None
        self.retained_earnings: Decimal | None = None

    def process_row(
        self,
        *,
        raw_label: str,
        value: Decimal | None,
        is_amount_blank: bool,
        raw_amount_str: str,
        prior_values: list[tuple[str, str | Decimal]],
        row_idx: int,
    ) -> None:
        norm_label = raw_label.lower()

        # 1. Section Headings (only when current amount is blank and no prior values)
        if is_amount_blank and not prior_values:
            matched_heading = False
            for sec_key, aliases in SECTION_HEADINGS.items():
                if norm_label in aliases:
                    matched_heading = True
                    if sec_key == "assets_root":
                        self.current_section = "assets"
                        self.current_subsection = None
                    elif sec_key == "assets_current":
                        self.current_section = "assets"
                        self.current_subsection = "current"
                    elif sec_key == "assets_non_current":
                        self.current_section = "assets"
                        self.current_subsection = "non_current"
                    elif sec_key == "liabilities_root":
                        self.current_section = "liabilities"
                        self.current_subsection = None
                    elif sec_key == "liabilities_current":
                        self.current_section = "liabilities"
                        self.current_subsection = "current"
                    elif sec_key == "liabilities_non_current":
                        self.current_section = "liabilities"
                        self.current_subsection = "non_current"
                    elif sec_key == "equity_root":
                        self.current_section = "equity"
                        self.current_subsection = None
                    break

            if matched_heading:
                return

        # 2. Prior period values into unmapped (Layout B)
        for raw_h, p_val in prior_values:
            p_val_str = str(p_val).replace(",", "")
            self.unmapped.append(
                UnmappedItem(
                    source_row=row_idx,
                    raw_label=raw_label,
                    raw_value=f"{raw_h}: {p_val_str}",
                    reason="prior_period_value",
                )
            )

        # 3. Check for reported totals
        if norm_label in REPORTED_TOTAL_LABELS["assets.total"]:
            self.assets_total = self.scalar_tracker.record_scalar(
                "assets.total", value, row_idx, raw_label, raw_amount_str
            )
            return
        elif norm_label in REPORTED_TOTAL_LABELS["liabilities.total"]:
            self.liabilities_total = self.scalar_tracker.record_scalar(
                "liabilities.total", value, row_idx, raw_label, raw_amount_str
            )
            return
        elif norm_label in REPORTED_TOTAL_LABELS["equity.total"]:
            self.equity_total = self.scalar_tracker.record_scalar(
                "equity.total", value, row_idx, raw_label, raw_amount_str
            )
            return

        # 4. Check for reported intermediate subtotals
        if norm_label in REPORTED_SUBTOTAL_LABELS:
            self.unmapped.append(
                UnmappedItem(
                    source_row=row_idx,
                    raw_label=raw_label,
                    raw_value=raw_amount_str,
                    reason="reported_subtotal",
                )
            )
            return

        # 5. Equity section items or labels matching equity canonical items
        if self.current_section == "equity" or any(
            norm_label in aliases for aliases in EQUITY_LINE_ITEMS.values()
        ):
            if any(norm_label == alias for alias in EQUITY_LINE_ITEMS["share_capital"]):
                self.share_capital = self.scalar_tracker.record_scalar(
                    "equity.share_capital", value, row_idx, raw_label, raw_amount_str
                )
            elif any(
                norm_label == alias for alias in EQUITY_LINE_ITEMS["retained_earnings"]
            ):
                self.retained_earnings = self.scalar_tracker.record_scalar(
                    "equity.retained_earnings",
                    value,
                    row_idx,
                    raw_label,
                    raw_amount_str,
                )
            else:
                if value is not None:
                    self.unmapped.append(
                        UnmappedItem(
                            source_row=row_idx,
                            raw_label=raw_label,
                            raw_value=raw_amount_str,
                            reason="unrecognized_financial_item",
                        )
                    )
                elif is_amount_blank and not prior_values:
                    self.unmapped.append(
                        UnmappedItem(
                            source_row=row_idx,
                            raw_label=raw_label,
                            raw_value="",
                            reason="unrecognized_note",
                        )
                    )
            return

        # 6. Assets section
        if self.current_section == "assets":
            canonical = None
            for can_field, aliases in CANONICAL_LINE_ITEMS["assets"].items():
                if norm_label in aliases:
                    canonical = can_field
                    break

            if canonical is not None:
                if self.current_subsection == "current":
                    self.assets_current.append(
                        LineItem(
                            canonical_field=canonical,
                            raw_label=raw_label,
                            value=value,
                            source_row=row_idx,
                        )
                    )
                elif self.current_subsection == "non_current":
                    self.assets_non_current.append(
                        LineItem(
                            canonical_field=canonical,
                            raw_label=raw_label,
                            value=value,
                            source_row=row_idx,
                        )
                    )
                else:
                    self.unmapped.append(
                        UnmappedItem(
                            source_row=row_idx,
                            raw_label=raw_label,
                            raw_value=raw_amount_str,
                            reason="ambiguous_section",
                        )
                    )
            else:
                if value is not None:
                    self.unmapped.append(
                        UnmappedItem(
                            source_row=row_idx,
                            raw_label=raw_label,
                            raw_value=raw_amount_str,
                            reason="unrecognized_financial_item",
                        )
                    )
                elif is_amount_blank and not prior_values:
                    self.unmapped.append(
                        UnmappedItem(
                            source_row=row_idx,
                            raw_label=raw_label,
                            raw_value="",
                            reason="unrecognized_note",
                        )
                    )
            return

        # 7. Liabilities section
        if self.current_section == "liabilities":
            canonical = None
            for can_field, aliases in CANONICAL_LINE_ITEMS["liabilities"].items():
                if norm_label in aliases:
                    canonical = can_field
                    break

            if canonical is not None:
                if self.current_subsection == "current":
                    self.liabilities_current.append(
                        LineItem(
                            canonical_field=canonical,
                            raw_label=raw_label,
                            value=value,
                            source_row=row_idx,
                        )
                    )
                elif self.current_subsection == "non_current":
                    self.liabilities_non_current.append(
                        LineItem(
                            canonical_field=canonical,
                            raw_label=raw_label,
                            value=value,
                            source_row=row_idx,
                        )
                    )
                else:
                    self.unmapped.append(
                        UnmappedItem(
                            source_row=row_idx,
                            raw_label=raw_label,
                            raw_value=raw_amount_str,
                            reason="ambiguous_section",
                        )
                    )
            else:
                if value is not None:
                    self.unmapped.append(
                        UnmappedItem(
                            source_row=row_idx,
                            raw_label=raw_label,
                            raw_value=raw_amount_str,
                            reason="unrecognized_financial_item",
                        )
                    )
                elif is_amount_blank and not prior_values:
                    self.unmapped.append(
                        UnmappedItem(
                            source_row=row_idx,
                            raw_label=raw_label,
                            raw_value="",
                            reason="unrecognized_note",
                        )
                    )
            return


def parse_balance_sheet_csv(content: bytes, *, document_id: UUID) -> BalanceSheet:
    """Parse Layout A or Layout B balance sheet CSV into a validated BalanceSheet model."""
    if len(content) > MAX_SOURCE_BYTES:
        raise ResourceLimitError(f"File size {len(content)} bytes exceeds 5 MiB limit")

    if not content.strip():
        raise InvalidStatementError("CSV file content is empty")

    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UnsupportedFormatError(
            "File must be valid UTF-8 or UTF-8 with BOM"
        ) from exc

    metadata_accumulator = MetadataAccumulator()
    layout_kind: str | None = None
    header_found = False

    assigned_cols: set[int] = set()
    particulars_col_idx: int = 0
    current_col_idx: int = 1
    prior_cols: list[tuple[date, int, str]] = []

    company: str | None = None
    reporting_date: date | None = None
    currency: str | None = None
    unit_scale: int | None = None
    source_locations: dict[str, SourceLocation] = {}
    unmapped: list[UnmappedItem] = []

    scalar_tracker: ScalarTracker | None = None
    state_machine: TableStateMachine | None = None

    reader = csv.reader(io.StringIO(decoded), strict=True)
    current_line = 0

    try:
        for row in reader:
            current_line = reader.line_num
            row_idx = current_line

            if row_idx > MAX_ROWS:
                raise ResourceLimitError(f"CSV row count exceeds {MAX_ROWS} row limit")
            if len(row) > MAX_COLUMNS:
                raise ResourceLimitError(
                    f"Row {row_idx} column count {len(row)} exceeds {MAX_COLUMNS} limit"
                )

            # Check cell length & formulas
            for cell in row:
                if len(cell) > MAX_CELL_CHARS:
                    raise ResourceLimitError(
                        f"CSV cell length exceeds limit of {MAX_CELL_CHARS} at row {row_idx}"
                    )
                if cell.strip().startswith("="):
                    raise InvalidStatementError(
                        f"Formula found in cell at row {row_idx}"
                    )

            # Skip completely empty rows
            if not any(c.strip() for c in row):
                continue

            # Before table header is found:
            if not header_found:
                # Check Layout A
                layout_a = _match_layout_a_header(row)
                if layout_a is not None:
                    header_found = True
                    layout_kind = "A"
                    particulars_col_idx = layout_a["particulars_col"]
                    current_col_idx = layout_a["amount_col"]
                    assigned_cols = {particulars_col_idx, current_col_idx}

                    (
                        company,
                        reporting_date,
                        currency,
                        unit_scale,
                        source_locations,
                        unmapped,
                    ) = metadata_accumulator.resolve()

                    scalar_tracker = ScalarTracker(source_locations, unmapped)
                    state_machine = TableStateMachine(
                        scalar_tracker, unmapped, source_locations
                    )
                    continue

                # Check Layout B
                layout_b = _match_layout_b_header(row)
                if layout_b is not None:
                    header_found = True
                    layout_kind = "B"
                    particulars_col_idx = layout_b["particulars_col"]
                    note_col = layout_b["note_col"]
                    dated_cols = layout_b["dated_cols"]

                    (
                        company,
                        reporting_date,
                        currency,
                        unit_scale,
                        source_locations,
                        unmapped,
                    ) = metadata_accumulator.resolve()

                    if reporting_date is None:
                        raise InvalidStatementError(
                            "Missing required reporting date in statement preamble before table header"
                        )

                    # Match declared reporting date against dated columns
                    matches = []
                    for d, col_idx, raw_h in dated_cols:
                        if d == reporting_date:
                            matches.append((d, col_idx, raw_h))
                        elif (
                            re.fullmatch(r"\d{4}", raw_h.strip())
                            and int(raw_h.strip()) == reporting_date.year
                        ):
                            matches.append((d, col_idx, raw_h))

                    if len(matches) == 0:
                        available = [raw_h for _, _, raw_h in dated_cols]
                        raise InvalidStatementError(
                            f"Declared reporting date '{reporting_date}' not found among statement columns: {available}"
                        )
                    if len(matches) > 1:
                        raise InvalidStatementError(
                            f"Duplicate period columns matching reporting date '{reporting_date}' in table header"
                        )

                    current_col_idx = matches[0][1]
                    prior_cols = [
                        (d, idx, raw_h)
                        for d, idx, raw_h in dated_cols
                        if idx != current_col_idx
                    ]

                    assigned_cols = {particulars_col_idx, current_col_idx}
                    if note_col is not None:
                        assigned_cols.add(note_col)
                    for _, p_idx, _ in prior_cols:
                        assigned_cols.add(p_idx)

                    scalar_tracker = ScalarTracker(source_locations, unmapped)
                    state_machine = TableStateMachine(
                        scalar_tracker, unmapped, source_locations
                    )
                    continue

                # Preamble metadata rows
                kvs = _extract_key_values(row)
                handled_any = False
                for k, v, _ in kvs:
                    if any(
                        alias in k
                        for alias in (
                            "company",
                            "entity",
                            "organization",
                            "name of company",
                        )
                    ):
                        metadata_accumulator.record_company(v, row_idx)
                        handled_any = True
                    elif any(
                        alias in k
                        for alias in (
                            "reporting date",
                            "as at",
                            "as on",
                            "balance sheet as of",
                            "period ended",
                            "date",
                        )
                    ):
                        metadata_accumulator.record_reporting_date(v, row_idx)
                        handled_any = True
                    elif any(
                        alias in k
                        for alias in ("currency", "reporting currency", "curr")
                    ):
                        metadata_accumulator.record_currency(k, v, row_idx)
                        handled_any = True
                    elif any(
                        alias in k
                        for alias in (
                            "amounts in",
                            "scale",
                            "units in",
                            "in",
                            "figures in",
                        )
                    ):
                        metadata_accumulator.record_unit_scale(k, v, row_idx)
                        handled_any = True
                    else:
                        metadata_accumulator.record_note(k, v, row_idx)
                        handled_any = True

                if not handled_any and any(c.strip() for c in row):
                    cell_text = " | ".join(c.strip() for c in row if c.strip())
                    metadata_accumulator.record_note(row[0].strip(), cell_text, row_idx)
                continue

            # After header found:
            assert state_machine is not None

            # Table shape validation: reject any populated cell in unassigned columns
            for col_idx, cell in enumerate(row):
                if col_idx not in assigned_cols and cell.strip():
                    raise InvalidStatementError(
                        f"Unexpected populated cell in unassigned column {col_idx} at row {row_idx}"
                    )

            raw_label = (
                row[particulars_col_idx].strip()
                if particulars_col_idx < len(row)
                else ""
            )
            raw_amount_str = (
                row[current_col_idx].strip() if current_col_idx < len(row) else ""
            )

            # Prior values (Layout B)
            prior_values: list[tuple[str, str]] = []
            if layout_kind == "B":
                for _, p_idx, raw_h in prior_cols:
                    p_val = row[p_idx].strip() if p_idx < len(row) else ""
                    if p_val:
                        if p_val.startswith("="):
                            raise InvalidStatementError(
                                f"Formula found in cell at row {row_idx}"
                            )
                        prior_values.append((raw_h, p_val))

            if not raw_label and not raw_amount_str and not prior_values:
                continue

            # Parse numeric value for current period (or None if missing)
            value: Decimal | None = None
            is_amount_blank = True
            if raw_amount_str:
                value = _parse_decimal(
                    raw_amount_str, source_row=row_idx, field_name=raw_label
                )
                is_amount_blank = False

            state_machine.process_row(
                raw_label=raw_label,
                value=value,
                is_amount_blank=is_amount_blank,
                raw_amount_str=raw_amount_str,
                prior_values=prior_values,
                row_idx=row_idx,
            )

    except csv.Error as exc:
        msg = str(exc)
        line_ref = reader.line_num if reader.line_num > 0 else (current_line + 1)
        if "field larger than field limit" in msg or "larger than field limit" in msg:
            raise ResourceLimitError(
                f"CSV cell length exceeds limit at row {line_ref}"
            ) from exc
        raise InvalidStatementError(f"Malformed CSV syntax at row {line_ref}") from exc

    if not header_found:
        raise UnsupportedFormatError(
            "Could not find valid Layout A ('Particulars,Amount') or Layout B ('Particulars,[Note No],<date>,<date>') table header"
        )

    if reporting_date is None:
        raise InvalidStatementError(
            "Missing required reporting date in statement preamble"
        )

    assert state_machine is not None
    return BalanceSheet(
        company=company,
        reporting_date=reporting_date,
        currency=currency,
        unit_scale=unit_scale,
        assets=SectionItems(
            current=state_machine.assets_current,
            non_current=state_machine.assets_non_current,
            total=state_machine.assets_total,
        ),
        liabilities=SectionItems(
            current=state_machine.liabilities_current,
            non_current=state_machine.liabilities_non_current,
            total=state_machine.liabilities_total,
        ),
        equity=Equity(
            share_capital=state_machine.share_capital,
            retained_earnings=state_machine.retained_earnings,
            total=state_machine.equity_total,
        ),
        unmapped=unmapped,
        source_metadata=SourceMetadata(
            document_id=document_id,
            sheet_name=None,
        ),
        source_locations=source_locations,
    )
