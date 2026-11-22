"""Check worksheet coordinates before OpenPyXL fills gaps with blank cells."""

from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries

from app.parsers.errors import ResourceLimitError

SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
MAX_WORKSHEET_ROWS = 20_000


def check_sheet_bounds(root, *, max_rows: int, max_columns: int) -> None:
    def check(row, column):
        if row is None or column is None or row < 1 or column < 1:
            raise ValueError("Invalid worksheet coordinate.")
        if row > max_rows or column > max_columns:
            raise ResourceLimitError("Worksheet coordinates exceed processing limits.")

    dimension = root.find(f"{SHEET_NS}dimension")
    if dimension is not None:
        left, top, right, bottom = range_boundaries(dimension.get("ref", ""))
        check(top, left)
        check(bottom, right)

    # Check actual cells too: a declared dimension may understate their positions.
    previous_row = 0
    for row in root.iter(f"{SHEET_NS}row"):
        row_number = int(row.get("r", previous_row + 1))
        check(row_number, 1)
        previous_row = row_number
        previous_column = 0
        for cell in row.findall(f"{SHEET_NS}c"):
            reference = cell.get("r")
            if reference:
                cell_row, column = coordinate_to_tuple(reference)
            else:
                cell_row, column = row_number, previous_column + 1
            check(cell_row, column)
            previous_column = column
