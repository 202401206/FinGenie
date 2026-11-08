"""Pure bank statement CSV parser using standard library csv and Decimal arithmetic."""

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
from app.schemas.bank_statement import (
    BankStatement,
    BankTransaction,
    SourceLocation,
    SourceMetadata,
    UnmappedItem,
)

MAX_SOURCE_BYTES = 5 * 1024 * 1024  # 5 MiB
MAX_TRANSACTION_ROWS = 10_000
MAX_COLUMNS = 50

# Recognized header aliases for column mapping
REQUIRED_HEADERS = {"date", "description", "debit", "credit", "balance"}

HEADER_ALIASES = {
    "date": [
        "date",
        "txn date",
        "transaction date",
        "value date",
        "trans date",
        "posting date",
    ],
    "description": [
        "description",
        "narration",
        "particulars",
        "details",
        "remarks",
        "transaction details",
        "transaction remarks",
    ],
    "debit": [
        "debit",
        "withdrawal",
        "dr",
        "withdrawals",
        "withdrawal (dr)",
        "withdrawals (dr)",
        "dr amount",
        "debit amount",
    ],
    "credit": [
        "credit",
        "deposit",
        "cr",
        "deposits",
        "deposit (cr)",
        "deposits (cr)",
        "cr amount",
        "credit amount",
    ],
    "balance": [
        "balance",
        "closing balance",
        "running balance",
        "net balance",
        "available balance",
        "account balance",
    ],
}


def _clean_str(val: str | None) -> str:
    return val.strip() if val else ""


def _parse_period_dates(raw: str) -> tuple[date, date] | None:
    """Extract start and end date from a string containing 'DATE to DATE' (ISO or DD/MM/YYYY)."""
    # Match ISO: YYYY-MM-DD to YYYY-MM-DD
    iso_match = re.search(r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", raw)
    if iso_match:
        try:
            return (
                datetime.strptime(iso_match.group(1), "%Y-%m-%d").date(),
                datetime.strptime(iso_match.group(2), "%Y-%m-%d").date(),
            )
        except ValueError:
            pass

    # Match delimited: DD/MM/YYYY to DD/MM/YYYY
    delim_match = re.search(r"(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})", raw)
    if delim_match:
        try:
            return (
                datetime.strptime(delim_match.group(1), "%d/%m/%Y").date(),
                datetime.strptime(delim_match.group(2), "%d/%m/%Y").date(),
            )
        except ValueError:
            pass

    return None


def _parse_decimal(
    raw: str, *, allow_negative: bool = False, source_row: int, field_name: str
) -> Decimal:
    """Parse exact monetary amount from string using Decimal without binary-float conversion."""
    cleaned = _clean_str(raw)
    if not cleaned:
        raise InvalidStatementError(
            f"Missing required numeric value for {field_name} at row {source_row}"
        )

    # Remove commas used as thousands separators (e.g. 10,000.00 -> 10000.00)
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

    if not allow_negative and amount < 0:
        raise InvalidStatementError(
            f"Negative amount '{raw}' not allowed for {field_name} magnitude at row {source_row}"
        )

    return amount


def _parse_date(raw: str, *, source_row: int) -> date:
    """Parse transaction date supporting ISO (YYYY-MM-DD) and common delimited formats."""
    cleaned = _clean_str(raw)
    if not cleaned:
        raise InvalidStatementError(f"Missing required date at row {source_row}")

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    raise InvalidStatementError(
        f"Invalid date format '{raw}' at row {source_row}; expected YYYY-MM-DD or DD/MM/YYYY"
    )


def _match_header_row(row: list[str]) -> dict[str, int] | None:
    """Check if row matches required table headers. Returns dict of field_name -> column_index."""
    col_map: dict[str, int] = {}
    normalized_row = [_clean_str(c).lower() for c in row]

    for field_name, aliases in HEADER_ALIASES.items():
        for idx, col in enumerate(normalized_row):
            if col in aliases and field_name not in col_map:
                col_map[field_name] = idx
                break

    if REQUIRED_HEADERS.issubset(col_map.keys()):
        return col_map
    return None


def _extract_key_values(record: list[str]) -> dict[str, str]:
    """Extract key-value pairs from a record where items are 'Key: Value' or adjacent cells 'Key', 'Value'."""
    kv: dict[str, str] = {}
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
                kv[k] = v
            i += 1
        else:
            k = cell.strip().lower()
            if i + 1 < len(record) and ":" not in record[i + 1]:
                kv[k] = record[i + 1].strip()
                i += 2
            else:
                kv[k] = ""
                i += 1
    return kv


def parse_bank_statement_csv(content: bytes, *, document_id: UUID) -> BankStatement:
    """Parse raw CSV bytes into a standardized, validated BankStatement."""
    if len(content) > MAX_SOURCE_BYTES:
        raise ResourceLimitError(
            f"Source file size ({len(content)} bytes) exceeds maximum allowed limit of {MAX_SOURCE_BYTES} bytes (5 MiB)"
        )

    if not content or not content.strip():
        raise InvalidStatementError("CSV file content is empty")

    # Decode using utf-8-sig to automatically handle both UTF-8 and UTF-8 with BOM
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UnsupportedFormatError(
            "Unsupported or malformed encoding. Expected UTF-8 encoded text."
        ) from exc

    # Use standard csv.reader to correctly parse quotes, embedded commas, and multiline cells
    csv_file = io.StringIO(text, newline="")
    reader = csv.reader(csv_file)

    header_map: dict[str, int] | None = None

    # Extracted metadata
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

    # Enumerate logical CSV records starting from 1 (including preamble/header)
    logical_row = 0

    for raw_record in reader:
        logical_row += 1

        if len(raw_record) > MAX_COLUMNS:
            raise ResourceLimitError(
                f"Row {logical_row} exceeds maximum allowed columns ({len(raw_record)} > {MAX_COLUMNS})"
            )

        # Ignore empty trailing or blank lines
        if not any(field.strip() for field in raw_record):
            continue

        clean_record = [_clean_str(c) for c in raw_record]

        # Phase 1: Search for table header if not found yet
        if header_map is None:
            matched_headers = _match_header_row(clean_record)
            if matched_headers:
                header_map = matched_headers
                continue

            # Parse preamble metadata above the transaction header
            kv = _extract_key_values(clean_record)
            joined_line = " ".join(clean_record)
            recognized = False

            for k, v in kv.items():
                if "bank" in k:
                    bank = v
                    source_locations["bank"] = SourceLocation(source_row=logical_row)
                    recognized = True
                elif "account holder" in k:
                    account_holder = v
                    source_locations["account_holder"] = SourceLocation(
                        source_row=logical_row
                    )
                    recognized = True
                elif "account type" in k:
                    account_type = v
                    source_locations["account_type"] = SourceLocation(
                        source_row=logical_row
                    )
                    recognized = True
                elif "currency" in k:
                    currency = v
                    source_locations["currency"] = SourceLocation(
                        source_row=logical_row
                    )
                    recognized = True
                elif "period" in k:
                    parsed_period = _parse_period_dates(v or joined_line)
                    if parsed_period:
                        period_start, period_end = parsed_period
                        source_locations["period_start"] = SourceLocation(
                            source_row=logical_row
                        )
                        source_locations["period_end"] = SourceLocation(
                            source_row=logical_row
                        )
                        recognized = True
                elif "opening balance" in k:
                    opening_balance = _parse_decimal(
                        v,
                        allow_negative=True,
                        source_row=logical_row,
                        field_name="opening_balance",
                    )
                    source_locations["opening_balance"] = SourceLocation(
                        source_row=logical_row
                    )
                    recognized = True

            if recognized:
                continue

            # Unrecognized preamble row
            unmapped.append(
                UnmappedItem(
                    source_row=logical_row,
                    raw_label=clean_record[0],
                    raw_value=" | ".join(clean_record[1:])
                    if len(clean_record) > 1
                    else clean_record[0],
                    reason="unknown_preamble_metadata",
                )
            )
            continue

        # Phase 2: Processing rows below table header (transactions, footer, or unmapped)
        first_cell = clean_record[0].lower()

        # Check for closing balance / footer summary
        if "closing balance" in first_cell or "total" in first_cell:
            kv = _extract_key_values(clean_record)
            closing_key = next((k for k in kv if "closing balance" in k), None)
            if closing_key:
                raw_amt = kv[closing_key]
                if not raw_amt and len(clean_record) > header_map["balance"]:
                    raw_amt = clean_record[header_map["balance"]]
                closing_balance = _parse_decimal(
                    raw_amt,
                    allow_negative=True,
                    source_row=logical_row,
                    field_name="closing_balance",
                )
                source_locations["closing_balance"] = SourceLocation(
                    source_row=logical_row
                )
                continue

            unmapped.append(
                UnmappedItem(
                    source_row=logical_row,
                    raw_label=clean_record[0],
                    raw_value=" | ".join(clean_record[1:]),
                    reason="footer_or_summary_row",
                )
            )
            continue

        # Check if row has enough columns for required headers
        max_required_col = max(header_map.values())
        if len(clean_record) <= max_required_col:
            raw_lbl = clean_record[0] if clean_record else "empty_row"
            raw_val = (
                " | ".join(clean_record[1:])
                if len(clean_record) > 1
                else (clean_record[0] if clean_record else "")
            )
            if len(clean_record) == 1 and ":" in clean_record[0]:
                raw_lbl, raw_val = clean_record[0].split(":", 1)
                raw_lbl = raw_lbl.strip()
                raw_val = raw_val.strip()

            unmapped.append(
                UnmappedItem(
                    source_row=logical_row,
                    raw_label=raw_lbl,
                    raw_value=raw_val,
                    reason="insufficient_columns_for_transaction",
                )
            )
            continue

        raw_date = clean_record[header_map["date"]]
        raw_desc = clean_record[header_map["description"]]
        raw_debit = clean_record[header_map["debit"]]
        raw_credit = clean_record[header_map["credit"]]
        raw_bal = clean_record[header_map["balance"]]

        # If date is not a valid date string, treat as unmapped rather than dropping or crashing
        try:
            tx_date = _parse_date(raw_date, source_row=logical_row)
        except InvalidStatementError:
            unmapped.append(
                UnmappedItem(
                    source_row=logical_row,
                    raw_label=clean_record[0],
                    raw_value=" | ".join(clean_record[1:])
                    if len(clean_record) > 1
                    else clean_record[0],
                    reason="invalid_or_missing_date",
                )
            )
            continue

        # Debit/Credit handling: in supported format, empty debit means 0, empty credit means 0
        if not raw_debit and not raw_credit:
            raise InvalidStatementError(
                f"Transaction at row {logical_row} has neither debit nor credit movement"
            )

        debit = (
            _parse_decimal(
                raw_debit,
                allow_negative=False,
                source_row=logical_row,
                field_name="debit",
            )
            if raw_debit
            else Decimal("0")
        )
        credit = (
            _parse_decimal(
                raw_credit,
                allow_negative=False,
                source_row=logical_row,
                field_name="credit",
            )
            if raw_credit
            else Decimal("0")
        )
        balance = _parse_decimal(
            raw_bal, allow_negative=True, source_row=logical_row, field_name="balance"
        )

        if not raw_desc:
            raise InvalidStatementError(
                f"Missing transaction description at row {logical_row}"
            )

        transactions.append(
            BankTransaction(
                date=tx_date,
                description=raw_desc,
                debit=debit,
                credit=credit,
                balance=balance,
                source_row=logical_row,
            )
        )

        if len(transactions) > MAX_TRANSACTION_ROWS:
            raise ResourceLimitError(
                f"Statement exceeds maximum allowed transaction limit of {MAX_TRANSACTION_ROWS} rows"
            )

    if header_map is None:
        raise UnsupportedFormatError(
            "Unsupported CSV layout: could not locate required transaction table headers (Date, Description, Debit, Credit, Balance)"
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
        source_metadata=SourceMetadata(document_id=document_id, sheet_name=None),
        source_locations=source_locations,
    )
