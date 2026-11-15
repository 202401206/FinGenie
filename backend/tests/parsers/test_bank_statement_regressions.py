"""Financial rows must not disappear, change type or bypass processing limits."""

import csv
import io
from datetime import date
from decimal import Decimal
from uuid import UUID
from xml.etree.ElementTree import fromstring, tostring
from zipfile import ZipFile

import pytest
from openpyxl import Workbook

from app.parsers.bank_statement import parse_bank_statement
from app.parsers.errors import InvalidStatementError, ResourceLimitError

DOCUMENT_ID = UUID("10000000-0000-4000-8000-000000000001")
HEADERS = ["Date", "Description", "Debit", "Credit", "Balance"]


def statement_bytes(rows, kind):
    if kind == "csv":
        stream = io.StringIO(newline="")
        csv.writer(stream).writerows(rows)
        return stream.getvalue().encode("utf-8")
    book = Workbook()
    for row in rows:
        book.active.append(row)
    stream = io.BytesIO()
    book.save(stream)
    book.close()
    return stream.getvalue()


def parse(rows, kind):
    return parse_bank_statement(
        statement_bytes(rows, kind), file_kind=kind, document_id=DOCUMENT_ID
    )


@pytest.mark.parametrize("valid_row_first", [False, True])
def test_short_financial_csv_row_rejects_the_whole_statement(valid_row_first):
    rows = [HEADERS]
    if valid_row_first:
        rows.append(["2026-01-01", "Valid row", "100", "0", "900"])
    rows.append(["2026-01-02", "Missing balance", "100", "0"])
    with pytest.raises(InvalidStatementError):
        parse(rows, "csv")


@pytest.mark.parametrize("kind", ["csv", "xlsx"])
@pytest.mark.parametrize(
    "description",
    [
        "Total petrol purchase",
        "Total",
        "Closing balance adjustment",
        "Closing Balance: fee",
    ],
)
def test_footer_words_in_a_description_do_not_remove_transactions(kind, description):
    statement = parse(
        [
            ["Description", "Date", "Debit", "Credit", "Balance"],
            [description, "2026-01-01", "100", "0", "900"],
            ["Closing Balance: 900"],
            ["Total"],
            ["Note: Synthetic end note"],
        ],
        kind,
    )
    assert len(statement.transactions) == 1
    assert statement.transactions[0].description == description
    assert statement.transactions[0].debit == Decimal("100")
    assert statement.transactions[0].source_row == 2
    assert statement.closing_balance == Decimal("900")
    assert [item.source_row for item in statement.unmapped] == [4, 5]


@pytest.mark.parametrize("kind", ["csv", "xlsx"])
@pytest.mark.parametrize(
    "duplicate",
    [
        "Debit",
        "Withdrawal",
        "Credit",
        "Deposit (Cr)",
        "Balance",
        "Net Balance",
        "Narration",
    ],
)
def test_duplicate_required_columns_and_aliases_are_rejected(kind, duplicate):
    with pytest.raises(InvalidStatementError):
        parse(
            [HEADERS + [duplicate], ["2026-01-01", "Rent", "0", "100", "900", "777"]],
            kind,
        )


@pytest.mark.parametrize("kind", ["csv", "xlsx"])
@pytest.mark.parametrize("value_date_first", [False, True])
def test_transaction_date_takes_precedence_over_the_separate_value_date(
    kind, value_date_first
):
    dates = ["Txn Date", "Value Date"]
    values = ["2026-01-01", "2026-01-02"]
    if value_date_first:
        dates.reverse()
        values.reverse()
    statement = parse([dates + HEADERS[1:], values + ["Rent", "100", "0", "900"]], kind)
    assert statement.transactions[0].date == date(2026, 1, 1)


@pytest.mark.parametrize("kind", ["csv", "xlsx"])
@pytest.mark.parametrize("second_date", ["Date", "Posting Date"])
def test_two_transaction_date_columns_are_ambiguous(kind, second_date):
    with pytest.raises(InvalidStatementError):
        parse(
            [
                HEADERS + [second_date],
                ["2026-01-01", "Rent", "100", "0", "900", "2026-01-02"],
            ],
            kind,
        )


@pytest.mark.parametrize("column", [2, 3, 4])
@pytest.mark.parametrize("value", [True, False])
def test_excel_boolean_money_is_rejected(column, value):
    row = ["2026-01-01", "Rent", 100, 0, 900]
    row[column] = value
    with pytest.raises(InvalidStatementError):
        parse([HEADERS, row], "xlsx")


@pytest.mark.parametrize("kind", ["csv", "xlsx"])
@pytest.mark.parametrize("debit_first", [False, True])
def test_short_nonfinancial_notes_still_keep_their_original_rows(kind, debit_first):
    headers = (
        HEADERS
        if not debit_first
        else ["Debit", "Date", "Description", "Credit", "Balance"]
    )
    row = (
        ["2026-01-01", "Rent", "100", "0", "900"]
        if not debit_first
        else ["100", "2026-01-01", "Rent", "0", "900"]
    )
    statement = parse(
        [headers, row, ["Note: Synthetic note"]],
        kind,
    )
    assert len(statement.transactions) == 1
    assert statement.unmapped[0].source_row == 3


@pytest.mark.parametrize("cover", [False, True])
@pytest.mark.parametrize("row,column", [(1_048_576, 1), (3, 16_384)])
@pytest.mark.parametrize("dimension", ["original", "understated", "missing"])
def test_sparse_coordinates_are_rejected_before_workbook_loading(
    monkeypatch, cover, row, column, dimension
):
    book = Workbook()
    book.active.append(HEADERS)
    book.active.append(["2026-01-01", "Rent", 100, 0, 900])
    sheet = book.create_sheet("Cover") if cover else book.active
    sheet.cell(row=row, column=column, value="Synthetic note")
    output = io.BytesIO()
    book.save(output)
    book.close()
    content = output.getvalue()
    if dimension != "original":
        rewritten = io.BytesIO()
        with ZipFile(io.BytesIO(content)) as source, ZipFile(rewritten, "w") as target:
            for member in source.infolist():
                data = source.read(member)
                if member.filename.startswith("xl/worksheets/"):
                    root = fromstring(data)
                    element = root.find(
                        "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}dimension"
                    )
                    if dimension == "missing":
                        root.remove(element)
                    else:
                        element.set("ref", "A1:E2")
                    data = tostring(root)
                target.writestr(member, data)
        content = rewritten.getvalue()

    def unexpected(*args, **kwargs):
        pytest.fail(
            "Unsafe worksheet coordinates must be rejected before loading cells."
        )

    monkeypatch.setattr(
        "app.parsers.bank_statement.xlsx_parser.openpyxl.load_workbook", unexpected
    )
    with pytest.raises(ResourceLimitError):
        parse_bank_statement(content, file_kind="xlsx", document_id=DOCUMENT_ID)
