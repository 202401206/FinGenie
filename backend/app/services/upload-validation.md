# Bounded bank-statement intake

## Working policy, 7 November 2026

Anshuman authorized implementation using the proposed guide defaults. These
are working development choices pending Shreyav/Frontend/Dhaval review. They do
not claim a team-wide approval or a deployed Storage configuration.

- Only bank statements for personal or business users.
- CSV uses UTF-8, optionally with a UTF-8 BOM, and comma-separated records.
- XLSX uses ordinary unencrypted, macro-free OOXML workbooks.
- Source bytes may be at most 5 MiB (5,242,880 bytes).
- Expanded XLSX content may be at most 25 MiB (26,214,400 bytes).
- The parser and save boundary enforce 10,000 actual transactions. Intake has a
  separate conservative cap of 20,000 populated CSV records/worksheet rows,
  including headers, preambles, covers and footers. CSV fields and populated
  XLSX cells per row are capped at 50.
- XLSX worksheet coordinates are also bounded to row 20,000 and column 50 (AX)
  on every sheet, including covers, blank gaps and styled cells. A small file
  with a distant cell is rejected before workbook loading. Both declared
  dimensions and actual row/cell references are checked; a false dimension does
  not bypass this limit. Custom policies can narrow the intake coordinate bounds;
  the parser retains its independent default ceiling.
- XLSX archives have at most 500 members, aligned with Dhaval's parser.
- Balance sheets are deferred and yield 422 unsupported_document_type in this
  helper. The broader endpoint plan still lists balance sheets for later work.

No specific bank layout is claimed. A structurally valid table can still be
rejected by the bank parser. The parser owns header/layout matching, required
financial values, date formats, formulas in required cells, sheet selection and
ambiguous-layout rejection. This helper does not calculate or normalize money.

## Interface

Call the asynchronous validate_upload helper after authenticating the caller.
Its arguments are a file supporting filename, content_type and async read(size),
plus user_type and document_type. A Starlette/FastAPI UploadFile is compatible.
UploadPolicy can be supplied explicitly to test or revise the working limits.

The result contains validated enums, a sanitized filename, SourceKind and the
original bounded bytes. Reuse those bytes for parsing and Storage. Source bytes
are excluded from the result's representation. The caller closes the file.

Reads request at most 64 KiB, or the remaining allowance plus one byte. Intake
stops on the first excess byte and does not drain an oversized file. An exact
5 MiB file is allowed by the byte bound, subject to the content checks.

The helper checks extension, MIME and actual content. Generic or missing MIME
is permitted only when content passes. CSV must contain a nonempty table with
at least two fields in a record. Strict CSV syntax and the standard CSV reader's
field-size bound apply. Plain prose, empty inputs, binary control bytes, PDF,
HTML/XML and JSON content are rejected.

XLSX checks required workbook parts and worksheet relationships. ZIP members are
never extracted. Both declared and actual expanded bytes are bounded and CRCs
are checked while reading. Duplicate names, traversal paths, symlinks, encryption,
binary/macro parts, unsupported compression, external relationships and unsafe
XML declarations are rejected. The pinned defusedxml package performs XML parsing
with DTDs, entities and external references disabled.

UploadValidationError exposes a safe status_code, code and message. A future
route should return message/code through FastAPI's detail wrapper.

| Status | Code | Condition |
| --- | --- | --- |
| 413 | file_too_large | Source byte limit exceeded |
| 415 | unsupported_file_type | Unsupported extension |
| 415 | file_type_mismatch | MIME contradicts extension |
| 422 | invalid_upload_fields | Invalid user/document enum |
| 422 | unsupported_document_type | Balance-sheet upload |
| 422 | invalid_filename | Missing/invalid/overlong filename |
| 422 | empty_file | Zero source bytes |
| 422 | invalid_file_content | Invalid encoding, table or XLSX container |
| 422 | file_resource_limit | Expanded bytes, archive entries, rows or columns exceed policy |

## Integration and evidence

Milestone 3 introduced these independent helpers. Milestone 4 now registers the
real upload route with Dhaval's parser and pinned multipart support. See
[upload orchestration](upload.md) for auth, request-body bounds and recovery.

The helper bounds bytes consumed from an UploadFile. The registered upload route
also enforces a whole multipart body budget before spooling and parses the body
after authentication. See the orchestration guide for exact limits.

Tests use synthetic CSV bytes and real generated XLSX containers. No live bank,
Supabase, Storage or parser integration is claimed.

Dependency reference:
https://pypi.org/project/defusedxml/0.7.1/
