"""Pure balance sheet XLSX parser using OpenPyXL with security bounds and exact Decimals."""

import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import openpyxl
from openpyxl.cell.cell import Cell

from app.parsers.balance_sheet.csv_parser import (
    CANONICAL_LINE_ITEMS,
    EQUITY_LINE_ITEMS,
    MAX_COLUMNS,
    MAX_ROWS,
    REPORTED_SUBTOTAL_LABELS,
    REPORTED_TOTAL_LABELS,
    SCALE_MAPPINGS,
    SECTION_HEADINGS,
    _extract_key_values,
    _match_layout_a_header,
    _match_layout_b_header,
    _parse_date,
    _parse_decimal,
)
from app.parsers.bank_statement.xlsx_limits import MAX_WORKSHEET_ROWS
from app.parsers.bank_statement.xlsx_parser import (
    _cell_is_formula,
    validate_xlsx_container,
)
from app.parsers.errors import (
    AmbiguousWorksheetError,
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


def _cell_to_str(cell: Cell) -> str:
    """Safely convert cell value to string, handling native dates and booleans."""
    if cell.value is None:
        return ""
    if isinstance(cell.value, (datetime, date)):
        return cell.value.strftime("%Y-%m-%d")
    return str(cell.value).strip()


def _xlsx_cell_to_decimal(
    cell: Cell, *, source_row: int, field_name: str
) -> Decimal | None:
    """Convert cell value directly to exact Decimal rejecting binary-float loss and formulas.

    OpenPyXL numeric cells may arrive as floats. We convert via Decimal(str(float))
    using shortest base-10 string representation. Lost IEEE-754 precision from
    original floating point representations cannot be restored.
    """
    if _cell_is_formula(cell):
        raise InvalidStatementError(
            f"Formulas are not supported in financial cells (found at row {source_row}, field '{field_name}')"
        )

    val = cell.value
    if val is None or val == "":
        return None

    if isinstance(val, bool):
        raise InvalidStatementError(
            f"Boolean value is not allowed for {field_name} at row {source_row}"
        )

    if isinstance(val, (int, Decimal)):
        return Decimal(val)

    if isinstance(val, float):
        amount = Decimal(str(val))
        if not amount.is_finite():
            raise InvalidStatementError(
                f"Non-finite numeric value at row {source_row} for {field_name}"
            )
        return amount

    # Text form numeric cell
    return _parse_decimal(str(val), source_row=source_row, field_name=field_name)


def _xlsx_cell_to_date(cell: Cell, *, source_row: int) -> date:
    """Extract normalized date from OpenPyXL date or string cell."""
    if _cell_is_formula(cell):
        raise InvalidStatementError(
            f"Formulas are not supported in date cells (found at row {source_row})"
        )

    val = cell.value
    if val is None or val == "":
        raise InvalidStatementError(
            f"Missing required reporting date at row {source_row}"
        )

    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val

    return _parse_date(str(val), source_row=source_row)


def _find_sheet_headers(
    ws: openpyxl.worksheet.worksheet.Worksheet,
) -> tuple[int, str, Any] | None:
    """Scan worksheet rows to find matching Layout A or Layout B table headers."""
    max_scan_row = min(ws.max_row or 0, 50)
    for row_idx, row in enumerate(
        ws.iter_rows(max_row=max_scan_row, values_only=False), start=1
    ):
        str_cells = [_cell_to_str(c) for c in row]

        # Check Layout A
        if _match_layout_a_header(str_cells):
            return row_idx, "A", None

        # Check Layout B
        layout_b = _match_layout_b_header(str_cells)
        if layout_b is not None:
            return row_idx, "B", layout_b

    return None


def parse_balance_sheet_xlsx(content: bytes, *, document_id: UUID) -> BalanceSheet:
    """Parse raw XLSX bytes into a standardized, validated BalanceSheet model."""
    # Step 1: Security container boundary checks
    validate_xlsx_container(content)

    # Step 2: Load workbook
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=False)
    except Exception as exc:
        raise UnsupportedFormatError(f"Unable to read XLSX workbook: {exc}") from exc

    try:
        # Step 3: Guard every sheet and select exactly one matching worksheet
        matching_sheets: list[
            tuple[openpyxl.worksheet.worksheet.Worksheet, int, str, Any]
        ] = []

        for sheet in wb.worksheets:
            if (sheet.max_row or 0) > MAX_WORKSHEET_ROWS or (
                sheet.max_column or 0
            ) > MAX_COLUMNS:
                raise ResourceLimitError(
                    "Worksheet coordinates exceed processing limits."
                )

            # Skip empty sheets
            if sheet.max_row is None or sheet.max_row == 0:
                continue

            header_info = _find_sheet_headers(sheet)
            if header_info is not None:
                matching_sheets.append(
                    (sheet, header_info[0], header_info[1], header_info[2])
                )

        if not matching_sheets:
            raise UnsupportedFormatError(
                "No worksheet matches the supported balance sheet layout"
            )

        if len(matching_sheets) > 1:
            matched_names = [s[0].title for s in matching_sheets]
            raise AmbiguousWorksheetError(
                f"Ambiguous workbook: multiple worksheets ({matched_names}) match the supported layout"
            )

        (
            selected_sheet,
            header_row_idx,
            layout_kind,
            layout_info,
        ) = matching_sheets[0]
        sheet_name = selected_sheet.title

        # Step 4: Extract metadata, line items, and unmapped entries
        company: str | None = None
        reporting_date: date | None = None
        currency: str | None = None
        unit_scale: int | None = None

        source_locations: dict[str, SourceLocation] = {}
        unmapped: list[UnmappedItem] = []

        # Sections
        current_section: str = "assets"
        current_subsection: str = "current"

        assets_current: list[LineItem] = []
        assets_non_current: list[LineItem] = []
        liabilities_current: list[LineItem] = []
        liabilities_non_current: list[LineItem] = []

        assets_total: Decimal | None = None
        liabilities_total: Decimal | None = None
        equity_total: Decimal | None = None

        share_capital: Decimal | None = None
        retained_earnings: Decimal | None = None

        particulars_col_idx = 0
        current_col_idx = 1
        prior_cols: list[tuple[date, int, str]] = []

        # Iterate all rows of the selected worksheet
        for row in selected_sheet.iter_rows(values_only=False):
            row_idx = row[0].row

            # Check bounds
            if row_idx > MAX_ROWS:
                raise ResourceLimitError(f"Row count exceeds {MAX_ROWS} row limit")
            if len(row) > MAX_COLUMNS:
                raise ResourceLimitError(
                    f"Row {row_idx} column count exceeds {MAX_COLUMNS} limit"
                )

            # Check for formula in any cell
            for cell in row:
                if _cell_is_formula(cell):
                    raise InvalidStatementError(
                        f"Formula found in cell at row {row_idx}: '{cell.value}'"
                    )

            str_cells = [_cell_to_str(c) for c in row]
            if not any(str_cells):
                continue

            # Before header: parse preamble metadata
            if row_idx < header_row_idx:
                kvs = _extract_key_values(str_cells)
                handled_any = False
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
                            source_locations["company"] = SourceLocation(
                                source_row=row_idx
                            )
                            handled_any = True

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
                            handled_any = True

                    # Currency
                    elif any(
                        curr_alias in k
                        for curr_alias in (
                            "currency",
                            "reporting currency",
                            "curr",
                        )
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
                        handled_any = True

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
                        handled_any = True

                    else:
                        unmapped.append(
                            UnmappedItem(
                                source_row=row_idx,
                                raw_label=k,
                                raw_value=v,
                                reason="unrecognized_note",
                            )
                        )
                        handled_any = True

                if not handled_any and any(str_cells):
                    cell_text = " | ".join(c for c in str_cells if c)
                    unmapped.append(
                        UnmappedItem(
                            source_row=row_idx,
                            raw_label=str_cells[0],
                            raw_value=cell_text,
                            reason="unrecognized_note",
                        )
                    )
                continue

            # Header row setup
            if row_idx == header_row_idx:
                if layout_kind == "A":
                    particulars_col_idx = 0
                    current_col_idx = 1
                elif layout_kind == "B":
                    particulars_col_idx = layout_info["particulars_col"]
                    dated_cols = layout_info["dated_cols"]

                    if reporting_date is None:
                        raise InvalidStatementError(
                            "Missing required reporting date in statement preamble before table header"
                        )

                    matches = []
                    for d, col_idx, raw_h in dated_cols:
                        if d == reporting_date:
                            matches.append((d, col_idx, raw_h))
                        elif (
                            raw_h.strip().isdigit()
                            and len(raw_h.strip()) == 4
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
                continue

            # Rows after header: line items, headings, totals
            raw_label = (
                str_cells[particulars_col_idx]
                if particulars_col_idx < len(str_cells)
                else ""
            )
            raw_amount_str = (
                str_cells[current_col_idx] if current_col_idx < len(str_cells) else ""
            )
            norm_label = raw_label.lower()

            # Prior values (Layout B)
            prior_values: list[tuple[str, Decimal]] = []
            if layout_kind == "B":
                for _, p_idx, raw_h in prior_cols:
                    if p_idx < len(row):
                        p_val = _xlsx_cell_to_decimal(
                            row[p_idx],
                            source_row=row_idx,
                            field_name=f"{raw_label} ({raw_h})",
                        )
                        if p_val is not None:
                            prior_values.append((raw_h, p_val))

            if not raw_label and not raw_amount_str and not prior_values:
                continue

            # Section headings (no current amount and no prior amounts)
            if not raw_amount_str and not prior_values:
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
                    unmapped.append(
                        UnmappedItem(
                            source_row=row_idx,
                            raw_label=raw_label,
                            raw_value="",
                            reason="unrecognized_note",
                        )
                    )
                continue

            # Preserve prior period values into unmapped (Layout B)
            for raw_h, p_val in prior_values:
                unmapped.append(
                    UnmappedItem(
                        source_row=row_idx,
                        raw_label=raw_label,
                        raw_value=f"{raw_h}: {p_val}",
                        reason="prior_period_value",
                    )
                )

            # Parse numeric value for current period
            current_cell = row[current_col_idx] if current_col_idx < len(row) else None
            value: Decimal | None = None
            if current_cell is not None and current_cell.value not in (
                None,
                "",
            ):
                value = _xlsx_cell_to_decimal(
                    current_cell, source_row=row_idx, field_name=raw_label
                )

            # Check for reported totals
            if norm_label in REPORTED_TOTAL_LABELS["assets.total"]:
                assets_total = value
                source_locations["assets.total"] = SourceLocation(source_row=row_idx)
                continue
            elif norm_label in REPORTED_TOTAL_LABELS["liabilities.total"]:
                liabilities_total = value
                source_locations["liabilities.total"] = SourceLocation(
                    source_row=row_idx
                )
                continue
            elif norm_label in REPORTED_TOTAL_LABELS["equity.total"]:
                equity_total = value
                source_locations["equity.total"] = SourceLocation(source_row=row_idx)
                continue

            # Intermediate section subtotals
            if norm_label in REPORTED_SUBTOTAL_LABELS:
                unmapped.append(
                    UnmappedItem(
                        source_row=row_idx,
                        raw_label=raw_label,
                        raw_value=raw_amount_str,
                        reason="reported_subtotal",
                    )
                )
                continue

            # Section-specific classification
            if current_section == "equity" or any(
                norm_label in aliases for aliases in EQUITY_LINE_ITEMS.values()
            ):
                if any(
                    norm_label == alias for alias in EQUITY_LINE_ITEMS["share_capital"]
                ):
                    share_capital = value
                    source_locations["equity.share_capital"] = SourceLocation(
                        source_row=row_idx
                    )
                elif any(
                    norm_label == alias
                    for alias in EQUITY_LINE_ITEMS["retained_earnings"]
                ):
                    retained_earnings = value
                    source_locations["equity.retained_earnings"] = SourceLocation(
                        source_row=row_idx
                    )
                else:
                    if value is not None:
                        unmapped.append(
                            UnmappedItem(
                                source_row=row_idx,
                                raw_label=raw_label,
                                raw_value=raw_amount_str,
                                reason="unrecognized_financial_item",
                            )
                        )

            elif current_section == "assets":
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
                    if value is not None:
                        unmapped.append(
                            UnmappedItem(
                                source_row=row_idx,
                                raw_label=raw_label,
                                raw_value=raw_amount_str,
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
                    if value is not None:
                        unmapped.append(
                            UnmappedItem(
                                source_row=row_idx,
                                raw_label=raw_label,
                                raw_value=raw_amount_str,
                                reason="unrecognized_financial_item",
                            )
                        )

        if reporting_date is None:
            raise InvalidStatementError(
                "Missing required reporting date in statement preamble"
            )

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
                sheet_name=sheet_name,
            ),
            source_locations=source_locations,
        )

    finally:
        wb.close()
