"""Pure balance sheet CSV parser using standard library csv and Decimal arithmetic."""

import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
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
        raise InvalidStatementError(
            f"Formula found in cell at row {source_row}: '{raw}'"
        )

    # Remove commas
    cleaned = cleaned.replace(",", "")

    # Handle parenthesized negative representation: (100.00) -> -100.00
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1].strip()}"

    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise InvalidStatementError(
            f"Invalid numeric value '{raw}' for {field_name} at row {source_row}"
        ) from exc

    if not amount.is_finite():
        raise InvalidStatementError(
            f"Non-finite numeric value '{raw}' for {field_name} at row {source_row}"
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
        f"Invalid reporting date format '{raw}' at row {source_row}; expected YYYY-MM-DD or DD/MM/YYYY"
    )


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


def _match_table_header(row: list[str]) -> bool:
    """Check if row matches Layout A table header (Particulars, Amount)."""
    clean_cells = [_clean_str(c).lower() for c in row if _clean_str(c)]
    if len(clean_cells) < 2:
        return False

    col0 = clean_cells[0]
    col1 = clean_cells[1]

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

    return col0 in particulars_aliases and col1 in amount_aliases


def parse_balance_sheet_csv(content: bytes, *, document_id: UUID) -> BalanceSheet:
    """Parse Layout A single-period balance sheet CSV into a validated BalanceSheet model."""
    if len(content) > MAX_SOURCE_BYTES:
        raise ResourceLimitError(f"File size {len(content)} bytes exceeds 5 MiB limit")

    # Empty content check
    if not content.strip():
        raise InvalidStatementError("CSV file content is empty")

    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UnsupportedFormatError(
            "File must be valid UTF-8 or UTF-8 with BOM"
        ) from exc

    reader = csv.reader(io.StringIO(decoded))

    # Preamble metadata accumulators
    company: str | None = None
    reporting_date: date | None = None
    currency: str | None = None
    unit_scale: int | None = None

    source_locations: dict[str, SourceLocation] = {}
    unmapped: list[UnmappedItem] = []

    # State tracking
    header_found = False

    # Sections
    current_section: str = "assets"  # "assets", "liabilities", "equity"
    current_subsection: str = "current"  # "current", "non_current"

    # Line item lists
    assets_current: list[LineItem] = []
    assets_non_current: list[LineItem] = []
    liabilities_current: list[LineItem] = []
    liabilities_non_current: list[LineItem] = []

    # Totals
    assets_total: Decimal | None = None
    liabilities_total: Decimal | None = None
    equity_total: Decimal | None = None

    # Equity items
    share_capital: Decimal | None = None
    retained_earnings: Decimal | None = None

    rows = list(reader)
    if len(rows) > MAX_ROWS:
        raise ResourceLimitError(
            f"CSV row count {len(rows)} exceeds {MAX_ROWS} row limit"
        )

    for row_idx, row in enumerate(rows, start=1):
        if len(row) > MAX_COLUMNS:
            raise ResourceLimitError(
                f"Row {row_idx} column count {len(row)} exceeds {MAX_COLUMNS} limit"
            )

        # Skip completely empty rows
        if not any(c.strip() for c in row):
            continue

        # Check for formulas in any cell
        for cell in row:
            if cell.strip().startswith("="):
                raise InvalidStatementError(
                    f"Formula found in cell at row {row_idx}: '{cell.strip()}'"
                )

        # Before header: parse preamble metadata
        if not header_found:
            # Check if this row is the table header
            if _match_table_header(row):
                header_found = True
                continue

            # Check if this is Layout B (dated columns)
            lower_cells = [_clean_str(c).lower() for c in row if _clean_str(c)]
            if len(lower_cells) >= 3 and any(
                re.match(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}", c) for c in lower_cells
            ):
                raise UnsupportedFormatError(
                    "Layout B (comparative balance sheet with dated columns) detected; "
                    "use Layout B comparative parser"
                )

            # Extract key: value pairs from preamble row
            kvs = _extract_key_values(row)
            for k, v, _ in kvs:
                # Company
                if any(
                    comp_alias in k
                    for comp_alias in (
                        "company",
                        "entity",
                        "organization",
                        "name of company",
                    )
                ):
                    if company is None and v:
                        company = v
                        source_locations["company"] = SourceLocation(source_row=row_idx)

                # Reporting Date
                elif any(
                    date_alias in k
                    for date_alias in (
                        "reporting date",
                        "as at",
                        "as on",
                        "balance sheet as of",
                        "period ended",
                        "date",
                    )
                ):
                    if reporting_date is None and v:
                        reporting_date = _parse_date(v, source_row=row_idx)
                        source_locations["reporting_date"] = SourceLocation(
                            source_row=row_idx
                        )

                # Currency
                elif any(
                    curr_alias in k
                    for curr_alias in ("currency", "reporting currency", "curr")
                ):
                    norm_curr = v.strip().upper()
                    if norm_curr in ("INR", "INDIAN RUPEES", "₹"):
                        currency = "INR"
                        source_locations["currency"] = SourceLocation(
                            source_row=row_idx
                        )
                    elif norm_curr in ("USD", "US DOLLARS"):
                        currency = "USD"
                        source_locations["currency"] = SourceLocation(
                            source_row=row_idx
                        )
                    elif norm_curr in ("RS.", "RS", "$"):
                        # Ambiguous currency
                        unmapped.append(
                            UnmappedItem(
                                source_row=row_idx,
                                raw_label=k,
                                raw_value=v,
                                reason="ambiguous_currency",
                            )
                        )
                    else:
                        raise InvalidStatementError(
                            f"Unsupported balance sheet currency '{v}' at row {row_idx}"
                        )

                # Unit Scale
                elif any(
                    scale_alias in k
                    for scale_alias in (
                        "amounts in",
                        "scale",
                        "units in",
                        "in",
                        "figures in",
                    )
                ):
                    scale_key = v.strip().lower()
                    if scale_key in SCALE_MAPPINGS:
                        unit_scale = SCALE_MAPPINGS[scale_key]
                        source_locations["unit_scale"] = SourceLocation(
                            source_row=row_idx
                        )
                    else:
                        unmapped.append(
                            UnmappedItem(
                                source_row=row_idx,
                                raw_label=k,
                                raw_value=v,
                                reason="ambiguous_unit_scale",
                            )
                        )
                else:
                    unmapped.append(
                        UnmappedItem(
                            source_row=row_idx,
                            raw_label=k,
                            raw_value=v,
                            reason="unrecognized_note",
                        )
                    )

            # Non-empty row that wasn't metadata or header
            if not kvs and any(c.strip() for c in row):
                cell_text = " | ".join(c.strip() for c in row if c.strip())
                unmapped.append(
                    UnmappedItem(
                        source_row=row_idx,
                        raw_label=row[0].strip(),
                        raw_value=cell_text,
                        reason="unrecognized_note",
                    )
                )
            continue

        # After header: process line items, section headings, and totals
        raw_label = row[0].strip() if len(row) > 0 else ""
        raw_amount = row[1].strip() if len(row) > 1 else ""
        norm_label = raw_label.lower()

        if not raw_label and not raw_amount:
            continue

        # Section Headings (rows with no amount or amount is empty)
        if not raw_amount:
            matched_heading = False
            for sec_key, aliases in SECTION_HEADINGS.items():
                if norm_label in aliases:
                    matched_heading = True
                    if sec_key == "assets_root":
                        current_section = "assets"
                    elif sec_key == "assets_current":
                        current_section = "assets"
                        current_subsection = "current"
                    elif sec_key == "assets_non_current":
                        current_section = "assets"
                        current_subsection = "non_current"
                    elif sec_key == "liabilities_root":
                        current_section = "liabilities"
                    elif sec_key == "liabilities_current":
                        current_section = "liabilities"
                        current_subsection = "current"
                    elif sec_key == "liabilities_non_current":
                        current_section = "liabilities"
                        current_subsection = "non_current"
                    elif sec_key == "equity_root":
                        current_section = "equity"
                    break

            if not matched_heading:
                # Group subheader or descriptive note
                unmapped.append(
                    UnmappedItem(
                        source_row=row_idx,
                        raw_label=raw_label,
                        raw_value="",
                        reason="unrecognized_note",
                    )
                )
            continue

        # Rows with an amount: parse numeric value
        value = _parse_decimal(raw_amount, source_row=row_idx, field_name=raw_label)

        # Check for reported totals
        if norm_label in REPORTED_TOTAL_LABELS["assets.total"]:
            assets_total = value
            source_locations["assets.total"] = SourceLocation(source_row=row_idx)
            continue
        elif norm_label in REPORTED_TOTAL_LABELS["liabilities.total"]:
            liabilities_total = value
            source_locations["liabilities.total"] = SourceLocation(source_row=row_idx)
            continue
        elif norm_label in REPORTED_TOTAL_LABELS["equity.total"]:
            equity_total = value
            source_locations["equity.total"] = SourceLocation(source_row=row_idx)
            continue

        # Check for reported intermediate subtotals (never count as leaf items)
        if norm_label in REPORTED_SUBTOTAL_LABELS:
            unmapped.append(
                UnmappedItem(
                    source_row=row_idx,
                    raw_label=raw_label,
                    raw_value=raw_amount,
                    reason="reported_subtotal",
                )
            )
            continue

        # Section-specific classification
        if current_section == "equity" or any(
            norm_label in aliases for aliases in EQUITY_LINE_ITEMS.values()
        ):
            if any(norm_label == alias for alias in EQUITY_LINE_ITEMS["share_capital"]):
                share_capital = value
                source_locations["equity.share_capital"] = SourceLocation(
                    source_row=row_idx
                )
            elif any(
                norm_label == alias for alias in EQUITY_LINE_ITEMS["retained_earnings"]
            ):
                retained_earnings = value
                source_locations["equity.retained_earnings"] = SourceLocation(
                    source_row=row_idx
                )
            else:
                unmapped.append(
                    UnmappedItem(
                        source_row=row_idx,
                        raw_label=raw_label,
                        raw_value=raw_amount,
                        reason="unrecognized_financial_item",
                    )
                )

        elif current_section == "assets":
            # Match canonical field
            canonical = None
            for can_field, aliases in CANONICAL_LINE_ITEMS["assets"].items():
                if norm_label in aliases:
                    canonical = can_field
                    break

            if canonical is not None:
                item = LineItem(
                    canonical_field=canonical,
                    raw_label=raw_label,
                    value=value,
                    source_row=row_idx,
                )
                if current_subsection == "current":
                    assets_current.append(item)
                else:
                    assets_non_current.append(item)
            else:
                unmapped.append(
                    UnmappedItem(
                        source_row=row_idx,
                        raw_label=raw_label,
                        raw_value=raw_amount,
                        reason="unrecognized_financial_item",
                    )
                )

        elif current_section == "liabilities":
            canonical = None
            for can_field, aliases in CANONICAL_LINE_ITEMS["liabilities"].items():
                if norm_label in aliases:
                    canonical = can_field
                    break

            if canonical is not None:
                item = LineItem(
                    canonical_field=canonical,
                    raw_label=raw_label,
                    value=value,
                    source_row=row_idx,
                )
                if current_subsection == "current":
                    liabilities_current.append(item)
                else:
                    liabilities_non_current.append(item)
            else:
                unmapped.append(
                    UnmappedItem(
                        source_row=row_idx,
                        raw_label=raw_label,
                        raw_value=raw_amount,
                        reason="unrecognized_financial_item",
                    )
                )

    if not header_found:
        raise UnsupportedFormatError(
            "Could not find valid Layout A balance sheet table header ('Particulars,Amount')"
        )

    if reporting_date is None:
        raise InvalidStatementError(
            "Missing required reporting date in statement preamble"
        )

    # Assemble validated models
    return BalanceSheet(
        company=company,
        reporting_date=reporting_date,
        currency=currency,
        unit_scale=unit_scale,
        assets=SectionItems(
            current=assets_current,
            non_current=assets_non_current,
            total=assets_total,
        ),
        liabilities=SectionItems(
            current=liabilities_current,
            non_current=liabilities_non_current,
            total=liabilities_total,
        ),
        equity=Equity(
            share_capital=share_capital,
            retained_earnings=retained_earnings,
            total=equity_total,
        ),
        unmapped=unmapped,
        source_metadata=SourceMetadata(
            document_id=document_id,
            sheet_name=None,
        ),
        source_locations=source_locations,
    )
