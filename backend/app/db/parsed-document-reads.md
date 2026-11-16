# Owned parsed-document reader

Sprint 2 analysis should read saved data through the existing `WorkspaceRepository`.
This is an internal reader, not a new public endpoint. Existing workspace list and
detail responses still exclude full parsed JSON.

## Exact dependency and imports

```python
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException

from app.db.dependencies import get_workspace_repository
from app.db.errors import (
    DatabaseUnauthorized,
    DatabaseUnavailable,
    DocumentNotReady,
    WorkspaceNotFound,
)
from app.db.parsed_read_models import ParsedDocumentContext
from app.db.repositories.workspaces import WorkspaceRepository
```

In Anshuman's async route, inject:

```python
repository: Annotated[WorkspaceRepository, Depends(get_workspace_repository)]
```

Then call Python inside the route, not inside Bash or PowerShell:

```python
context: ParsedDocumentContext = await repository.get_parsed_document(workspace_id)
```

Use this read dependency, not `get_parsed_document_repository`, which is the
existing write/finalization dependency. Do not construct a repository using a
user ID from request parameters. No new package dependency is needed.

## Return model

`ParsedDocumentContext` is a frozen dataclass with these fields:

| Field | Python type |
| --- | --- |
| `workspace` | `app.db.models.WorkspaceRecord` |
| `document_id` | `uuid.UUID` |
| `parsed_json` | `app.db.parsed_models.ParsedBankStatement` or `app.db.parsed_read_models.ParsedBalanceSheet` |

The owned workspace's `document_type` selects the validation model. The reader
checks that the stored document belongs to that workspace and that the parsed
source metadata's document UUID matches the stored document UUID.

For analysis helpers expecting dictionaries, use:

```python
statement_data = context.parsed_json.model_dump(mode="python")
```

This keeps monetary values as `Decimal`. Do not call `float()` or use
`model_dump(mode="json")` as an intermediate step for calculations. Pydantic's
default JSON serialization turns Decimal into strings; the API team must preserve
the agreed response contract when serializing calculated results.

Bank data uses the existing validated save model. Balance data validates the
agreed stored contract: company, reporting date, currency, unit scale, asset and
liability sections, equity, unmapped data, and source metadata/locations. It does
not implement the balance parser or enable balance uploads/finalization.

Nulls and unknown fields are preserved. Amounts are never scaled in the reader.
Scale/reliability decisions and reconciliation belong to analysis. A financial
mismatch is not repaired or rejected here just to make totals agree.

## Errors to translate in the route

All exceptions below are imported from `app.db.errors`.

| Exception | Suggested HTTP response |
| --- | --- |
| `WorkspaceNotFound` | 404, `workspace_not_found`; identical for absent and foreign workspaces |
| `DocumentNotReady` | 409, `document_not_ready`; owned workspace has no document, no parsed result, or uploaded/failed status |
| `DatabaseUnauthorized` | 401, safe `unauthorized` detail and `WWW-Authenticate: Bearer` |
| `DatabaseUnavailable` | 503, safe `database_unavailable` detail; includes corrupt/mismatched stored data and dependency failures |

For example, translate readiness as:

```python
try:
    context = await repository.get_parsed_document(workspace_id)
except DocumentNotReady:
    raise HTTPException(
        status_code=409,
        detail={
            "code": "document_not_ready",
            "message": "The document is not ready for analysis.",
        },
    ) from None
```

Handle the other three exceptions using the table as well. Do not catch every
exception and turn it into 404 or 409. Invalid UUID path parameters should be
validated by FastAPI with `workspace_id: UUID`.

The existing authentication dependencies already reject missing/invalid tokens
before repository access and translate Auth service outages. A 401 after that
check can still occur if the token expires before the Data API read.

## Ownership and precision

The existing dependency obtains the verified user's UUID and original access
token. Workspace lookup filters on both workspace ID and verified user ID before
any document lookup. Every request sends that caller's JWT through the existing
publishable-key client, leaving RLS active. There is no service-role fallback,
shared mutable session, new RPC, or policy/schema change.

JSON numeric fractions decode directly as `Decimal` before Pydantic validation.
Integer financial values also validate as Decimal. No binary float intermediate
is used, including for preserved nested fields.

## Verification

`tests/db/test_parsed_document_reads.py` contains 24 synthetic tests covering both
document types, exact high-precision amounts, negative balances, zero/null values,
unknown fields, missing/foreign workspaces, readiness, mismatched IDs/types,
multiple documents, malformed responses, network/auth/dependency failures, and
the actual authentication/dependency wiring across users.

The full backend suite passed: 900 tests. Ruff checks and formatting passed for
the changed Python files. One existing Starlette TestClient deprecation warning
remains. Tests use mocked HTTP transports, not live accounts; they verify caller
scoping without claiming to revalidate deployed RLS. No database migration is
needed for this reader.
