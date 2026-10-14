# Parsers - Backend team

`bank_statement/` and `balance_sheet/` will parse the corresponding document types;
`common/` will hold genuinely shared file/header/unit utilities. CSV/XLSX only.
Validate before parsing and against shared schemas afterward. Preserve unknown
content, original rows and reported units. Add synthetic input fixtures and tests
in `tests/parsers/` as each supported format is implemented. No parser exists yet.
