"""Bounded, side-effect-free intake checks before bank parsing or persistence."""

import csv
import io
import posixpath
import stat
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Protocol
from xml.etree.ElementTree import ParseError
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile
from zlib import error as ZlibError

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring

from app.schemas.common import DocumentType, UserType
from app.services.source_models import SourceAttempt, SourceKind

CHUNK_BYTES = 64 * 1024
SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
TYPE_NS = "{http://schemas.openxmlformats.org/package/2006/content-types}"
WORKBOOK_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
)


@dataclass(frozen=True)
class UploadPolicy:
    """Working defaults authorized for implementation; see upload-validation.md."""

    max_bytes: int = 5 * 1024 * 1024
    max_rows: int = 10_000
    max_columns: int = 50
    max_expanded_bytes: int = 25 * 1024 * 1024
    max_zip_members: int = 500
    max_records: int = 20_000

    def __post_init__(self) -> None:
        if any(type(value) is not int or value <= 0 for value in vars(self).values()):
            raise ValueError("Upload limits must be positive integers.")


DEFAULT_POLICY = UploadPolicy()


class UploadValidationError(Exception):
    """Safe error data for a future route to translate into HTTP responses."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class UploadReader(Protocol):
    filename: str | None
    content_type: str | None

    async def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True)
class ValidatedUpload:
    user_type: UserType
    document_type: DocumentType
    filename: str
    kind: SourceKind
    content: bytes = field(repr=False)


def invalid_content() -> UploadValidationError:
    return UploadValidationError(
        422, "invalid_file_content", "The file is not a valid supported CSV or XLSX."
    )


def resource_limit() -> UploadValidationError:
    return UploadValidationError(
        422, "file_resource_limit", "The file exceeds the supported processing limits."
    )


def validate_fields(
    user_type: str, document_type: str
) -> tuple[UserType, DocumentType]:
    try:
        user = UserType(user_type)
        document = DocumentType(document_type)
    except ValueError:
        raise UploadValidationError(
            422,
            "invalid_upload_fields",
            "Valid user_type and document_type are required.",
        ) from None
    if document != DocumentType.BANK_STATEMENT:
        raise UploadValidationError(
            422, "unsupported_document_type", "Only bank statements are supported."
        )
    return user, document


async def read_bounded(source: UploadReader, policy: UploadPolicy) -> bytes:
    content = bytearray()
    while True:
        # One byte beyond the bound detects overflow without draining the upload.
        size = min(CHUNK_BYTES, policy.max_bytes - len(content) + 1)
        chunk = await source.read(size)
        if len(chunk) > size:
            raise invalid_content()
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > policy.max_bytes:
            raise UploadValidationError(
                413, "file_too_large", "The file exceeds the supported upload size."
            )
    if not content:
        raise UploadValidationError(422, "empty_file", "The uploaded file is empty.")
    return bytes(content)


def validate_file_metadata(
    filename: str | None, content_type: str | None
) -> tuple[str, SourceKind]:
    if not filename:
        raise UploadValidationError(422, "invalid_filename", "A filename is required.")
    try:
        filename = str(SourceAttempt.sanitize_filename(filename))
    except ValueError:
        raise UploadValidationError(
            422, "invalid_filename", "A valid filename is required."
        ) from None
    if len(filename) > 255:
        raise UploadValidationError(
            422, "invalid_filename", "The filename is too long."
        )
    suffix = PurePosixPath(filename).suffix.lower()
    kinds = {".csv": SourceKind.CSV, ".xlsx": SourceKind.XLSX}
    if suffix not in kinds:
        raise UploadValidationError(
            415, "unsupported_file_type", "Only CSV and XLSX files are supported."
        )
    kind = kinds[suffix]
    allowed = {
        SourceKind.CSV: {
            "text/csv",
            "application/csv",
            "text/plain",
            "application/vnd.ms-excel",
        },
        SourceKind.XLSX: {SourceKind.XLSX.content_type},
    }
    # Browsers can omit MIME or use a generic binary type. Content is still checked.
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if mime not in allowed[kind] | {"", "application/octet-stream"}:
        raise UploadValidationError(
            415, "file_type_mismatch", "The file type does not match its extension."
        )
    return filename, kind


def inspect_csv(content: bytes, policy: UploadPolicy) -> None:
    try:
        text = content.decode("utf-8-sig")
        if any(ord(char) < 32 and char not in "\t\r\n" for char in text):
            raise invalid_content()
        if text.lstrip().startswith(("%PDF-", "PK\x03\x04", "<", "{", "[")):
            raise invalid_content()
        count = 0
        table = False
        for row in csv.reader(io.StringIO(text, newline=""), strict=True):
            if not any(cell.strip() for cell in row):
                continue
            count += 1
            if count > policy.max_records or len(row) > policy.max_columns:
                raise resource_limit()
            table = table or len(row) > 1
        if not table:
            raise invalid_content()
    except (UnicodeDecodeError, csv.Error):
        raise invalid_content() from None


def inspect_sheet(root, policy: UploadPolicy) -> bool:
    if root.tag != f"{SHEET_NS}worksheet":
        raise invalid_content()
    populated_rows = 0
    populated = False
    for row in root.iter(f"{SHEET_NS}row"):
        cells = [
            cell
            for cell in row.findall(f"{SHEET_NS}c")
            if any(
                child.tag in {f"{SHEET_NS}v", f"{SHEET_NS}is", f"{SHEET_NS}f"}
                for child in cell
            )
        ]
        if cells:
            populated = True
            populated_rows += 1
        if populated_rows > policy.max_records or len(cells) > policy.max_columns:
            raise resource_limit()
    return populated


def inspect_xlsx(content: bytes, policy: UploadPolicy) -> None:
    if not content.startswith(b"PK\x03\x04"):
        raise invalid_content()
    try:
        with ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > policy.max_zip_members:
                raise resource_limit()
            names = [member.filename for member in members]
            required = {
                "[Content_Types].xml",
                "xl/workbook.xml",
                "xl/_rels/workbook.xml.rels",
            }
            if len(set(names)) != len(names) or not required.issubset(names):
                raise invalid_content()
            if sum(member.file_size for member in members) > policy.max_expanded_bytes:
                raise resource_limit()
            expanded = 0
            roots = {}
            populated_sheets = set()
            sheet_names = set()
            for member in members:
                path = PurePosixPath(member.filename)
                if (
                    "\\" in member.filename
                    or path.is_absolute()
                    or ".." in path.parts
                    or member.flag_bits & 1
                    or stat.S_ISLNK(member.external_attr >> 16)
                    or member.compress_type not in {ZIP_STORED, ZIP_DEFLATED}
                    or member.filename.lower().endswith(".bin")
                ):
                    raise invalid_content()
                # Verify actual expansion/CRC in bounded reads, without extracting.
                data = bytearray()
                with archive.open(member) as stream:
                    while chunk := stream.read(
                        min(CHUNK_BYTES, policy.max_expanded_bytes - expanded + 1)
                    ):
                        expanded += len(chunk)
                        if expanded > policy.max_expanded_bytes:
                            raise resource_limit()
                        if member.filename.endswith((".xml", ".rels")):
                            data.extend(chunk)
                if not data:
                    continue
                root = fromstring(bytes(data), forbid_dtd=True)
                if member.filename in required:
                    roots[member.filename] = root
                if member.filename.endswith(".rels"):
                    for rel in root:
                        if rel.get("TargetMode", "").lower() == "external":
                            raise invalid_content()
                if member.filename.startswith(
                    "xl/worksheets/"
                ) and member.filename.endswith(".xml"):
                    sheet_names.add(member.filename)
                    if inspect_sheet(root, policy):
                        populated_sheets.add(member.filename)

            types = roots["[Content_Types].xml"]
            if types.tag != f"{TYPE_NS}Types" or not any(
                item.get("PartName") == "/xl/workbook.xml"
                and item.get("ContentType") == WORKBOOK_TYPE
                for item in types
            ):
                raise invalid_content()
            workbook = roots["xl/workbook.xml"]
            if workbook.tag != f"{SHEET_NS}workbook":
                raise invalid_content()
            rels = roots["xl/_rels/workbook.xml.rels"]
            if rels.tag != f"{REL_NS}Relationships":
                raise invalid_content()
            targets = {}
            for rel in rels:
                target = rel.get("Target", "")
                resolved = (
                    target.lstrip("/")
                    if target.startswith("/")
                    else posixpath.normpath(posixpath.join("xl", target))
                )
                targets[rel.get("Id")] = resolved
            linked = set()
            for sheet in workbook.iter(f"{SHEET_NS}sheet"):
                relation = sheet.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                )
                target = targets.get(relation)
                if target not in sheet_names:
                    raise invalid_content()
                linked.add(target)
            if not linked.intersection(populated_sheets):
                raise invalid_content()
    except (
        BadZipFile,
        ParseError,
        DefusedXmlException,
        KeyError,
        OSError,
        RuntimeError,
        NotImplementedError,
        ValueError,
        ZlibError,
    ):
        raise invalid_content() from None


async def validate_upload(
    file: UploadReader,
    *,
    user_type: str,
    document_type: str,
    policy: UploadPolicy = DEFAULT_POLICY,
) -> ValidatedUpload:
    """Consumes the file once. Caller authenticates first and owns file cleanup."""
    user, document = validate_fields(user_type, document_type)
    filename, kind = validate_file_metadata(file.filename, file.content_type)
    content = await read_bounded(file, policy)
    if kind == SourceKind.CSV:
        inspect_csv(content, policy)
    else:
        inspect_xlsx(content, policy)
    return ValidatedUpload(user, document, filename, kind, content)
