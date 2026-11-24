"""Pure balance sheet XLSX parser using OpenPyXL with security bounds and exact Decimals."""

import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import openpyxl
from openpyxl.cell.cell import Cell

from app.parsers.balance_sheet.csv_parser import (
    MAX_COLUMNS,
    MAX_ROWS,
    MetadataAccumulator,
    ScalarTracker,
    TableStateMachine,
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
        layout_a = _match_layout_a_header(str_cells)
        if layout_a is not None:
            return row_idx, "A", layout_a

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

        metadata_accumulator = MetadataAccumulator()

        particulars_col_idx = 0
        current_col_idx = 1
        prior_cols: list[tuple[date, int, str]] = []
        assigned_cols: set[int] = set()

        company: str | None = None
        reporting_date: date | None = None
        currency: str | None = None
        unit_scale: int | None = None
        source_locations: dict[str, SourceLocation] = {}
        unmapped: list[UnmappedItem] = []

        scalar_tracker: ScalarTracker | None = None
        state_machine: TableStateMachine | None = None

        for row in selected_sheet.iter_rows(values_only=False):
            row_idx = row[0].row

            if row_idx > MAX_ROWS:
                raise ResourceLimitError(f"Row count exceeds {MAX_ROWS} row limit")
            if len(row) > MAX_COLUMNS:
                raise ResourceLimitError(
                    f"Row {row_idx} column count exceeds {MAX_COLUMNS} limit"
                )

            # Check formulas in any cell
            for cell in row:
                if _cell_is_formula(cell):
                    raise InvalidStatementError(
                        f"Formula found in cell at row {row_idx}"
                    )

            str_cells = [_cell_to_str(c) for c in row]
            if not any(str_cells):
                continue

            # Before header: parse preamble metadata
            if row_idx < header_row_idx:
                kvs = _extract_key_values(str_cells)
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

                if not handled_any and any(str_cells):
                    cell_text = " | ".join(c for c in str_cells if c)
                    metadata_accumulator.record_note(str_cells[0], cell_text, row_idx)
                continue

            # Header row setup
            if row_idx == header_row_idx:
                (
                    company,
                    reporting_date,
                    currency,
                    unit_scale,
                    source_locations,
                    unmapped,
                ) = metadata_accumulator.resolve()

                if layout_kind == "A":
                    particulars_col_idx = layout_info["particulars_col"]
                    current_col_idx = layout_info["amount_col"]
                    assigned_cols = {particulars_col_idx, current_col_idx}
                elif layout_kind == "B":
                    particulars_col_idx = layout_info["particulars_col"]
                    note_col = layout_info["note_col"]
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

            # Rows after header: line items, headings, totals
            assert state_machine is not None

            # Table shape validation: reject any populated cell in unassigned columns
            for col_idx, cell in enumerate(row):
                if col_idx not in assigned_cols:
                    val_str = _cell_to_str(cell)
                    if val_str:
                        raise InvalidStatementError(
                            f"Unexpected populated cell in unassigned column {col_idx} at row {row_idx}"
                        )

            raw_label = (
                str_cells[particulars_col_idx]
                if particulars_col_idx < len(str_cells)
                else ""
            )
            raw_amount_str = (
                str_cells[current_col_idx] if current_col_idx < len(str_cells) else ""
            )

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

            # Parse numeric value for current period
            current_cell = row[current_col_idx] if current_col_idx < len(row) else None
            value: Decimal | None = None
            is_amount_blank = True
            if current_cell is not None and current_cell.value not in (None, ""):
                value = _xlsx_cell_to_decimal(
                    current_cell, source_row=row_idx, field_name=raw_label
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
                sheet_name=sheet_name,
            ),
            source_locations=source_locations,
        )

    finally:
        wb.close()
