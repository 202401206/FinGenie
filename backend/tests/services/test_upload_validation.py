"""Synthetic upload intake boundaries, without Auth, database or parser calls."""

import asyncio
import io
import warnings
from dataclasses import replace
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from openpyxl import Workbook
from starlette.datastructures import Headers, UploadFile

from app.services.source_models import SourceKind
from app.services.upload_validation import (
    CHUNK_BYTES,
    DEFAULT_POLICY,
    UploadPolicy,
    UploadValidationError,
    inspect_csv,
    inspect_xlsx,
    read_bounded,
    validate_upload,
)


class TrackedUpload:
    def __init__(self, content, filename="statement.csv", content_type="text/csv"):
        self.stream = io.BytesIO(content)
        self.filename = filename
        self.content_type = content_type
        self.reads = []

    async def read(self, size=-1):
        assert 0 < size <= CHUNK_BYTES
        self.reads.append(size)
        return self.stream.read(size)


def validate(source, **changes):
    return asyncio.run(
        validate_upload(
            source,
            user_type=changes.pop("user_type", "personal"),
            document_type=changes.pop("document_type", "bank_statement"),
            **changes,
        )
    )


def xlsx(rows=None):
    book = Workbook()
    for row in rows if rows is not None else [["Date", "Credit"], ["2026-01-01", 12]]:
        book.active.append(row)
    output = io.BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def edit_zip(content, changes):
    output = io.BytesIO()
    with (
        ZipFile(io.BytesIO(content)) as original,
        ZipFile(output, "w", ZIP_DEFLATED) as updated,
    ):
        for member in original.infolist():
            if member.filename not in changes:
                updated.writestr(member, original.read(member))
        for name, value in changes.items():
            if value is not None:
                updated.writestr(name, value)
    return output.getvalue()


@pytest.mark.parametrize("user", ["personal", "business"])
@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
def test_csv_intake_preserves_bytes_and_sanitizes_filename(user, bom):
    content = (
        bom + b'Date,Description,Credit\r\n2026-01-01,"Line one\nLine two",12.30\r\n'
    )
    source = TrackedUpload(
        content, "C:\\private\\statement.CSV", "text/csv; charset=utf-8"
    )
    result = validate(source, user_type=user)
    assert result.content == content
    assert result.filename == "statement.CSV"
    assert result.kind == SourceKind.CSV
    assert result.user_type == user


def test_accepts_real_starlette_upload_file_without_multipart_dependency():
    source = UploadFile(
        io.BytesIO(b"a,b\n1,2\n"),
        filename="statement.csv",
        headers=Headers({"content-type": "text/csv"}),
    )
    try:
        assert validate(source).content == b"a,b\n1,2\n"
    finally:
        asyncio.run(source.close())


@pytest.mark.parametrize(
    "size", [DEFAULT_POLICY.max_bytes - 1, DEFAULT_POLICY.max_bytes]
)
def test_byte_limit_accepts_exact_boundary(size):
    source = TrackedUpload(b"x" * size)
    assert len(asyncio.run(read_bounded(source, DEFAULT_POLICY))) == size
    assert max(source.reads) <= CHUNK_BYTES


def test_overflow_stops_after_one_extra_byte_without_draining():
    source = TrackedUpload(b"x" * (DEFAULT_POLICY.max_bytes + CHUNK_BYTES))
    with pytest.raises(UploadValidationError) as caught:
        asyncio.run(read_bounded(source, DEFAULT_POLICY))
    assert (caught.value.status_code, caught.value.code) == (413, "file_too_large")
    assert source.stream.tell() == DEFAULT_POLICY.max_bytes + 1
    assert source.stream.read(1) == b"x"


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"user_type": "current"}, "invalid_upload_fields"),
        ({"user_type": ""}, "invalid_upload_fields"),
        ({"document_type": "pdf"}, "invalid_upload_fields"),
        ({"document_type": "balance_sheet"}, "unsupported_document_type"),
        (
            {"user_type": "business", "document_type": "balance_sheet"},
            "unsupported_document_type",
        ),
    ],
)
def test_invalid_fields_are_rejected_before_reading(changes, code):
    source = TrackedUpload(b"a,b")
    with pytest.raises(UploadValidationError) as caught:
        validate(source, **changes)
    assert (caught.value.status_code, caught.value.code) == (422, code)
    assert source.reads == []


@pytest.mark.parametrize(
    "filename,mime,status",
    [
        (None, "text/csv", 422),
        ("..", "text/csv", 422),
        ("x" * 256 + ".csv", "text/csv", 422),
        ("statement.pdf", "application/pdf", 415),
        ("statement.xls", "application/vnd.ms-excel", 415),
        ("statement.xlsm", "application/octet-stream", 415),
        ("statement.csv", "application/pdf", 415),
        ("statement.xlsx", "text/csv", 415),
        ("statement.csv.exe", "text/csv", 415),
    ],
)
def test_invalid_metadata_is_rejected_before_reading(filename, mime, status):
    source = TrackedUpload(b"a,b", filename, mime)
    with pytest.raises(UploadValidationError) as caught:
        validate(source)
    assert caught.value.status_code == status
    assert source.reads == []


@pytest.mark.parametrize(
    "mime", [None, "", "application/octet-stream", "application/vnd.ms-excel"]
)
def test_generic_csv_mime_still_checks_contents(mime):
    assert (
        validate(TrackedUpload(b"a,b\n1,2", content_type=mime)).kind == SourceKind.CSV
    )
    with pytest.raises(UploadValidationError):
        validate(TrackedUpload(b"%PDF-1.7\nprivate", content_type=mime))


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"   \n",
        b"\xef\xbb\xbf",
        b"not a table",
        b"%PDF-1.7\nprivate",
        b"\xff\xfeA\x00",
        b"a,b\n1,\x00",
        b'a,b\n1,"unfinished',
        b"<html>a,b</html>",
        b'{"a":1,"b":2}',
    ],
)
def test_empty_binary_or_malformed_csv_produces_safe_error(content):
    with pytest.raises(UploadValidationError) as caught:
        validate(TrackedUpload(content))
    assert caught.value.status_code == 422
    assert str(caught.value) in {
        "The uploaded file is empty.",
        "The file is not a valid supported CSV or XLSX.",
    }
    assert "private" not in str(caught.value)


def test_quoted_multiline_csv_counts_records_not_physical_lines():
    inspect_csv(
        b'a,b\n1,"line\nline"\n', UploadPolicy(max_rows=1, max_columns=2, max_records=2)
    )


@pytest.mark.parametrize("rows", [1, 2])
def test_csv_row_count_boundary(rows):
    policy = UploadPolicy(max_rows=1, max_records=2)
    content = b"a,b\n" + b"1,2\n" * rows
    if rows == 1:
        inspect_csv(content, policy)
    else:
        with pytest.raises(UploadValidationError) as caught:
            inspect_csv(content, policy)
        assert caught.value.code == "file_resource_limit"


@pytest.mark.parametrize("columns", [50, 51])
def test_csv_column_count_boundary(columns):
    content = (",".join(["a"] * columns) + "\n").encode()
    if columns == 50:
        inspect_csv(content, DEFAULT_POLICY)
    else:
        with pytest.raises(UploadValidationError):
            inspect_csv(content, DEFAULT_POLICY)


def test_xlsx_intake_preserves_real_workbook_bytes():
    content = xlsx()
    result = validate(
        TrackedUpload(content, "statement.xlsx", SourceKind.XLSX.content_type)
    )
    assert result.content == content
    assert result.kind == SourceKind.XLSX


@pytest.mark.parametrize(
    "content", [b"a,b\n1,2", b"%PDF-1.7\nprivate", b"PK\x03\x04broken"]
)
def test_renamed_files_are_not_xlsx(content):
    with pytest.raises(UploadValidationError) as caught:
        validate(TrackedUpload(content, "statement.xlsx", None))
    assert caught.value.status_code == 422


def test_xlsx_renamed_to_csv_is_rejected():
    with pytest.raises(UploadValidationError):
        validate(TrackedUpload(xlsx()))


@pytest.mark.parametrize(
    "changes",
    [
        {"[Content_Types].xml": None},
        {"xl/workbook.xml": b"broken XML"},
        {"xl/_rels/workbook.xml.rels": None},
        {"xl/worksheets/sheet1.xml": b"<worksheet/>"},
        {"xl/worksheets/sheet1.xml": None},
        {"../escape.xml": b"<root/>"},
        {"xl/vbaProject.bin": b"macro"},
        {"xl/unsafe.xml": b'<!DOCTYPE x [<!ENTITY e "boom">]><x>&e;</x>'},
        {
            "xl/_rels/external.xml.rels": b'<Relationships><Relationship TargetMode="External" Target="https://example.test"/></Relationships>'
        },
    ],
)
def test_malformed_or_unsafe_xlsx_is_rejected(changes):
    content = edit_zip(xlsx(), changes)
    with pytest.raises(UploadValidationError) as caught:
        inspect_xlsx(content, DEFAULT_POLICY)
    assert (caught.value.status_code, caught.value.code) == (
        422,
        "invalid_file_content",
    )


def test_arbitrary_zip_is_rejected():
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("statement.csv", b"a,b\n1,2")
    with pytest.raises(UploadValidationError):
        inspect_xlsx(output.getvalue(), DEFAULT_POLICY)


def test_duplicate_xlsx_entries_are_rejected():
    output = io.BytesIO(xlsx())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(output, "a") as archive:
            archive.writestr("xl/workbook.xml", b"<workbook/>")
    with pytest.raises(UploadValidationError):
        inspect_xlsx(output.getvalue(), DEFAULT_POLICY)


def test_expanded_archive_exact_limit_and_one_byte_over():
    content = xlsx()
    with ZipFile(io.BytesIO(content)) as archive:
        total = sum(member.file_size for member in archive.infolist())
    inspect_xlsx(content, replace(DEFAULT_POLICY, max_expanded_bytes=total))
    with pytest.raises(UploadValidationError) as caught:
        inspect_xlsx(content, replace(DEFAULT_POLICY, max_expanded_bytes=total - 1))
    assert caught.value.code == "file_resource_limit"


def test_highly_compressed_xlsx_member_is_bounded():
    content = edit_zip(xlsx(), {"padding.txt": b"x" * 1_000_000})
    assert len(content) < DEFAULT_POLICY.max_bytes
    with pytest.raises(UploadValidationError) as caught:
        inspect_xlsx(content, replace(DEFAULT_POLICY, max_expanded_bytes=100_000))
    assert caught.value.code == "file_resource_limit"


def test_zip_member_count_is_bounded():
    with pytest.raises(UploadValidationError) as caught:
        inspect_xlsx(xlsx(), replace(DEFAULT_POLICY, max_zip_members=1))
    assert caught.value.code == "file_resource_limit"


@pytest.mark.parametrize("columns", [50, 51])
def test_xlsx_populated_column_boundary(columns):
    content = xlsx([["header"] * columns, [1] * columns])
    if columns == 50:
        inspect_xlsx(content, DEFAULT_POLICY)
    else:
        with pytest.raises(UploadValidationError) as caught:
            inspect_xlsx(content, DEFAULT_POLICY)
        assert caught.value.code == "file_resource_limit"


@pytest.mark.parametrize("rows", [1, 2])
def test_xlsx_populated_row_boundary(rows):
    content = xlsx([["a", "b"]] + [[1, 2]] * rows)
    policy = replace(DEFAULT_POLICY, max_rows=1, max_records=2)
    if rows == 1:
        inspect_xlsx(content, policy)
    else:
        with pytest.raises(UploadValidationError) as caught:
            inspect_xlsx(content, policy)
        assert caught.value.code == "file_resource_limit"


def test_empty_workbook_is_rejected():
    with pytest.raises(UploadValidationError):
        inspect_xlsx(xlsx([]), DEFAULT_POLICY)


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_invalid_internal_policy_is_rejected(value):
    with pytest.raises(ValueError):
        UploadPolicy(max_bytes=value)


def test_validation_result_repr_does_not_dump_source_content():
    result = validate(TrackedUpload(b"private_header,b\nprivate_value,2"))
    assert "private_value" not in repr(result)


def test_xlsx_with_pdf_prefix_is_rejected():
    with pytest.raises(UploadValidationError):
        inspect_xlsx(b"%PDF-1.7\n" + xlsx(), DEFAULT_POLICY)


def test_symbolic_link_in_archive_is_rejected():
    from zipfile import ZipInfo

    output = io.BytesIO(xlsx())
    member = ZipInfo("link")
    member.create_system = 3
    member.external_attr = 0o120777 << 16
    with ZipFile(output, "a") as archive:
        archive.writestr(member, "target")
    with pytest.raises(UploadValidationError):
        inspect_xlsx(output.getvalue(), DEFAULT_POLICY)


def test_truncated_zip_is_a_safe_error():
    with pytest.raises(UploadValidationError) as caught:
        inspect_xlsx(xlsx()[:-30], DEFAULT_POLICY)
    assert str(caught.value) == "The file is not a valid supported CSV or XLSX."


def test_short_reader_chunks_do_not_cause_premature_eof():
    class ShortReads(TrackedUpload):
        async def read(self, size=-1):
            return await super().read(min(size, 2))

    assert validate(ShortReads(b"a,b\n1,2\n")).content == b"a,b\n1,2\n"


def test_invalid_uploads_do_not_echo_private_filename_or_content():
    with pytest.raises(UploadValidationError) as caught:
        validate(TrackedUpload(b"%PDF-private", "private-account.csv"))
    assert "private" not in str(caught.value)
