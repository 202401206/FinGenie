"""Pure bank statement XLSX parser using OpenPyXL with security bounds and exact Decimals."""

import io
import zipfile
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import openpyxl
from openpyxl.cell.cell import Cell

from app.parsers.bank_statement.csv_parser import (
    HEADER_ALIASES,
    MAX_COLUMNS,
    MAX_SOURCE_BYTES,
    MAX_TRANSACTION_ROWS,
    REQUIRED_HEADERS,
    _extract_key_values,
    _parse_date,
    _parse_decimal,
    _parse_period_dates,
)
from app.parsers.errors import (
    AmbiguousWorksheetError,
    InvalidStatementError,
    ResourceLimitError,
    UnsupportedFormatError,
)
from app.schemas.bank_statement import (
    BankStatement,
    BankTransaction,
    SourceLocation,
    SourceMetadata,
    UnmappedItem,
)

MAX_UNCOMPRESSED_BYTES = 25 * 1024 * 1024  # 25 MiB expanded size limit
MAX_ZIP_ENTRIES = 500


def validate_xlsx_container(content: bytes) -> None:
    """Validate that content is a safe, bounded XLSX archive without macros or zip bombs."""
    if len(content) > MAX_SOURCE_BYTES:
        raise ResourceLimitError(
            f"Source file size ({len(content)} bytes) exceeds maximum allowed limit of {MAX_SOURCE_BYTES} bytes (5 MiB)"
        )

    if not content.startswith(b"PK\x03\x04"):
        raise UnsupportedFormatError("File is not a valid XLSX workbook archive")

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            total_uncompressed = 0
            entry_count = len(zf.infolist())

            if entry_count > MAX_ZIP_ENTRIES:
                raise ResourceLimitError(
                    f"XLSX archive contains too many entries ({entry_count} > {MAX_ZIP_ENTRIES})"
                )

            has_workbook = False
            for zinfo in zf.infolist():
                # Check for macro components
                if "vbaProject.bin" in zinfo.filename:
                    raise UnsupportedFormatError(
                        "Macro-enabled workbooks (.xlsm) are not supported"
                    )

                total_uncompressed += zinfo.file_size
                if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                    raise ResourceLimitError(
                        f"Expanded XLSX content ({total_uncompressed} bytes) exceeds limit of {MAX_UNCOMPRESSED_BYTES} bytes (25 MiB)"
                    )

                if (
                    "xl/workbook.xml" in zinfo.filename
                    or "[Content_Types].xml" in zinfo.filename
                ):
                    has_workbook = True

            if not has_workbook:
                raise UnsupportedFormatError(
                    "Corrupted XLSX archive: missing workbook structure"
                )

    except zipfile.BadZipFile as exc:
        raise UnsupportedFormatError("Malformed or corrupted XLSX file") from exc


def _cell_is_formula(cell: Cell) -> bool:
    """Check if cell is a formula calculation rather than a literal value."""
    if cell.data_type == "f":
        return True
    if isinstance(cell.value, str) and cell.value.strip().startswith("="):
        return True
    return False


def _cell_to_str(cell: Cell) -> str:
    """Safely convert cell value to trimmed string."""
    if cell.value is None:
        return ""
    if isinstance(cell.value, (datetime, date)):
        return cell.value.strftime("%Y-%m-%d")
    return str(cell.value).strip()


def _cell_to_decimal(
    cell: Cell, *, allow_negative: bool, source_row: int, field_name: str
) -> Decimal:
    """Convert cell value directly to exact Decimal rejecting binary-float loss and formulas."""
    if _cell_is_formula(cell):
        raise InvalidStatementError(
            f"Formulas are not supported in financial cells (found at row {source_row}, field '{field_name}')"
        )

    val = cell.value
    if val is None or val == "":
        raise InvalidStatementError(
            f"Missing required numeric value for {field_name} at row {source_row}"
        )

    if isinstance(val, (int, Decimal)):
        amount = Decimal(val)
        if not allow_negative and amount < 0:
            raise InvalidStatementError(
                f"Negative amount not allowed for {field_name} magnitude at row {source_row}"
            )
        return amount

    if isinstance(val, float):
        # Convert float using shortest string representation to preserve base-10 digits
        amount = Decimal(str(val))
        if not amount.is_finite():
            raise InvalidStatementError(
                f"Non-finite value at row {source_row} for {field_name}"
            )
        if not allow_negative and amount < 0:
            raise InvalidStatementError(
                f"Negative amount not allowed for {field_name} magnitude at row {source_row}"
            )
        return amount

    # Text form monetary cell
    return _parse_decimal(
        str(val),
        allow_negative=allow_negative,
        source_row=source_row,
        field_name=field_name,
    )


def _cell_to_date(cell: Cell, *, source_row: int) -> date:
    """Extract normalized date from OpenPyXL date or string cell."""
    if _cell_is_formula(cell):
        raise InvalidStatementError(
            f"Formulas are not supported in date cells (found at row {source_row})"
        )

    val = cell.value
    if val is None or val == "":
        raise InvalidStatementError(f"Missing required date at row {source_row}")

    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val

    return _parse_date(str(val), source_row=source_row)


def _find_sheet_headers(
    ws: openpyxl.worksheet.worksheet.Worksheet,
) -> tuple[int, dict[str, int]] | None:
    """Scan worksheet rows to find matching transaction table headers."""
    for row_idx, row in enumerate(ws.iter_rows(values_only=False), start=1):
        if row_idx > 50:  # Bound header search to first 50 rows
            break
        row_str_cells = [_cell_to_str(c).lower() for c in row]
        col_map: dict[str, int] = {}
        for field_name, aliases in HEADER_ALIASES.items():
            for col_idx, col in enumerate(row_str_cells):
                if col in aliases and field_name not in col_map:
                    col_map[field_name] = col_idx
                    break
        if REQUIRED_HEADERS.issubset(col_map.keys()):
            return row_idx, col_map
    return None


def parse_bank_statement_xlsx(content: bytes, *, document_id: UUID) -> BankStatement:
    """Parse raw XLSX bytes into a standardized, validated BankStatement."""
    # Step 1: Security container boundary checks
    validate_xlsx_container(content)

    # Step 2: Load workbook
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=False)
    except Exception as exc:
        raise UnsupportedFormatError(f"Unable to read XLSX workbook: {exc}") from exc

    # Step 3: Select exactly one matching worksheet
    matching_sheets: list[
        tuple[openpyxl.worksheet.worksheet.Worksheet, int, dict[str, int]]
    ] = []

    for sheet in wb.worksheets:
        # Ignore empty sheets
        if sheet.max_row is None or sheet.max_row == 0:
            continue
        header_info = _find_sheet_headers(sheet)
        if header_info is not None:
            matching_sheets.append((sheet, header_info[0], header_info[1]))

    if not matching_sheets:
        raise UnsupportedFormatError(
            "No worksheet matches the supported bank statement layout"
        )

    if len(matching_sheets) > 1:
        matched_names = [s[0].title for s in matching_sheets]
        raise AmbiguousWorksheetError(
            f"Ambiguous workbook: multiple worksheets ({matched_names}) match the supported layout"
        )

    selected_sheet, header_row_idx, header_map = matching_sheets[0]
    sheet_name = selected_sheet.title

    # Step 4: Extract metadata, transactions, and unmapped rows
    bank: str | None = None
    account_holder: str | None = None
    account_type: str | None = None
    currency: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    opening_balance: Decimal | None = None
    closing_balance: Decimal | None = None

    source_locations: dict[str, SourceLocation] = {}
    transactions: list[BankTransaction] = []
    unmapped: list[UnmappedItem] = []

    for row_idx, row in enumerate(selected_sheet.iter_rows(values_only=False), start=1):
        if len(row) > MAX_COLUMNS:
            raise ResourceLimitError(
                f"Row {row_idx} exceeds maximum allowed columns ({len(row)} > {MAX_COLUMNS})"
            )

        str_cells = [_cell_to_str(c) for c in row]
        if not any(c for c in str_cells):
            continue

        # Phase 1: Preamble metadata (above header_row_idx)
        if row_idx < header_row_idx:
            kv = _extract_key_values(str_cells)
            joined_line = " ".join(str_cells)
            recognized = False

            for k, v in kv.items():
                if "bank" in k:
                    bank = v
                    source_locations["bank"] = SourceLocation(source_row=row_idx)
                    recognized = True
                elif "account holder" in k:
                    account_holder = v
                    source_locations["account_holder"] = SourceLocation(
                        source_row=row_idx
                    )
                    recognized = True
                elif "account type" in k:
                    account_type = v
                    source_locations["account_type"] = SourceLocation(
                        source_row=row_idx
                    )
                    recognized = True
                elif "currency" in k:
                    currency = v
                    source_locations["currency"] = SourceLocation(source_row=row_idx)
                    recognized = True
                elif "period" in k:
                    parsed_period = _parse_period_dates(v or joined_line)
                    if parsed_period:
                        period_start, period_end = parsed_period
                        source_locations["period_start"] = SourceLocation(
                            source_row=row_idx
                        )
                        source_locations["period_end"] = SourceLocation(
                            source_row=row_idx
                        )
                        recognized = True
                elif "opening balance" in k:
                    opening_balance = _parse_decimal(
                        v,
                        allow_negative=True,
                        source_row=row_idx,
                        field_name="opening_balance",
                    )
                    source_locations["opening_balance"] = SourceLocation(
                        source_row=row_idx
                    )
                    recognized = True

            if recognized:
                continue

            non_empty_tail = [c for c in str_cells[1:] if c]
            unmapped.append(
                UnmappedItem(
                    source_row=row_idx,
                    raw_label=str_cells[0],
                    raw_value=" | ".join(non_empty_tail)
                    if non_empty_tail
                    else str_cells[0],
                    reason="unknown_preamble_metadata",
                )
            )
            continue

        # Header row itself: skip
        if row_idx == header_row_idx:
            continue

        # Phase 2: Transaction rows & footer rows (below header_row_idx)
        first_cell_lower = str_cells[0].lower()

        # Check for closing balance / footer summary
        if "closing balance" in first_cell_lower or "total" in first_cell_lower:
            kv = _extract_key_values(str_cells)
            closing_key = next((k for k in kv if "closing balance" in k), None)
            if closing_key:
                raw_amt = kv[closing_key]
                if not raw_amt and len(row) > header_map["balance"]:
                    raw_amt = _cell_to_str(row[header_map["balance"]])
                closing_balance = _parse_decimal(
                    raw_amt,
                    allow_negative=True,
                    source_row=row_idx,
                    field_name="closing_balance",
                )
                source_locations["closing_balance"] = SourceLocation(source_row=row_idx)
                continue

            non_empty_tail = [c for c in str_cells[1:] if c]
            unmapped.append(
                UnmappedItem(
                    source_row=row_idx,
                    raw_label=str_cells[0],
                    raw_value=" | ".join(non_empty_tail)
                    if non_empty_tail
                    else str_cells[0],
                    reason="footer_or_summary_row",
                )
            )
            continue

        max_required_col = max(header_map.values())
        if len(row) <= max_required_col:
            non_empty_tail = [c for c in str_cells[1:] if c]
            raw_lbl = str_cells[0] if str_cells else "empty_row"
            raw_val = (
                " | ".join(non_empty_tail)
                if non_empty_tail
                else (str_cells[0] if str_cells else "")
            )
            if (not non_empty_tail) and str_cells and ":" in str_cells[0]:
                raw_lbl, raw_val = str_cells[0].split(":", 1)
                raw_lbl = raw_lbl.strip()
                raw_val = raw_val.strip()

            unmapped.append(
                UnmappedItem(
                    source_row=row_idx,
                    raw_label=raw_lbl,
                    raw_value=raw_val,
                    reason="insufficient_columns_for_transaction",
                )
            )
            continue

        date_cell = row[header_map["date"]]
        desc_cell = row[header_map["description"]]
        debit_cell = row[header_map["debit"]]
        credit_cell = row[header_map["credit"]]
        balance_cell = row[header_map["balance"]]

        # Extract date
        try:
            tx_date = _cell_to_date(date_cell, source_row=row_idx)
        except InvalidStatementError:
            # iter_rows pads metadata rows with empty cells. Keep those notes,
            # but reject malformed dates/formulas on rows with financial values.
            if any(
                cell.value not in (None, "")
                for cell in (debit_cell, credit_cell, balance_cell)
            ):
                raise
            non_empty_tail = [c for c in str_cells[1:] if c]
            unmapped.append(
                UnmappedItem(
                    source_row=row_idx,
                    raw_label=str_cells[0],
                    raw_value=" | ".join(non_empty_tail)
                    if non_empty_tail
                    else str_cells[0],
                    reason="invalid_or_missing_date",
                )
            )
            continue

        # Check movement: empty debit or empty credit means 0
        debit_empty = debit_cell.value is None or debit_cell.value == ""
        credit_empty = credit_cell.value is None or credit_cell.value == ""

        if debit_empty and credit_empty:
            raise InvalidStatementError(
                f"Transaction at row {row_idx} has neither debit nor credit movement"
            )

        debit = (
            Decimal("0")
            if debit_empty
            else _cell_to_decimal(
                debit_cell, allow_negative=False, source_row=row_idx, field_name="debit"
            )
        )
        credit = (
            Decimal("0")
            if credit_empty
            else _cell_to_decimal(
                credit_cell,
                allow_negative=False,
                source_row=row_idx,
                field_name="credit",
            )
        )
        balance = _cell_to_decimal(
            balance_cell, allow_negative=True, source_row=row_idx, field_name="balance"
        )

        description = _cell_to_str(desc_cell)
        if not description:
            raise InvalidStatementError(
                f"Missing transaction description at row {row_idx}"
            )

        transactions.append(
            BankTransaction(
                date=tx_date,
                description=description,
                debit=debit,
                credit=credit,
                balance=balance,
                source_row=row_idx,
            )
        )

        if len(transactions) > MAX_TRANSACTION_ROWS:
            raise ResourceLimitError(
                f"Statement exceeds maximum allowed transaction limit of {MAX_TRANSACTION_ROWS} rows"
            )

    return BankStatement(
        bank=bank,
        account_holder=account_holder,
        account_type=account_type,
        currency=currency,
        period_start=period_start,
        period_end=period_end,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        transactions=transactions,
        unmapped=unmapped,
        source_metadata=SourceMetadata(document_id=document_id, sheet_name=sheet_name),
        source_locations=source_locations,
    )
