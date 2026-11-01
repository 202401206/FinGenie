# Database - Backend team

Focused database queries live in `repositories/`. Review `docs/database-schema.md`
before adding SQL or Supabase access. Initial tables, RLS and private Storage
policies are in `supabase/migrations/`.

## Workspace reads

`WorkspaceRepository` in `repositories/workspaces.py` implements:

| Method | Result |
| --- | --- |
| `list_workspaces(*, limit=50, offset=0)` | `Page[WorkspaceRecord]`, scoped to the verified owner |
| `get_workspace(workspace_id)` | `WorkspaceDetails`, containing the workspace and document metadata |
| `list_transactions(workspace_id, *, limit=50, offset=0)` | `Page[TransactionRecord]`, after resolving the owned workspace/document |

`Page` has `items`, `limit`, `offset`, and `total`. Limit must be 1-100; offset must
be nonnegative. Lists request an exact filtered count and sort by
`created_at DESC, id DESC` for workspaces and `source_row ASC, id ASC` for
transactions. Past-end pages return an empty list while preserving the total.
An owned workspace with no document has no transactions; balance sheets raise
`UnsupportedDocumentType`. No new document readiness rule is introduced here.

Reads use explicit column lists. Document results exclude storage paths and
`parsed_json`; optional metadata remains `None`. Amounts decode directly from JSON
numbers into finite `Decimal` values, including negative balances, without first
passing through a float. These are database read models in `models.py`, not API
response schemas. The API owner must preserve the numeric JSON contract when
mapping them: Pydantic's default Decimal serialization emits strings, and converting
to float can lose precision. Review and test the actual response bytes together.

## Connecting routes

Inject `get_workspace_repository` from `dependencies.py` using FastAPI's `Depends`.
It verifies the user using the existing `require_user`, then supplies the same
request's original token and HTTP client to the repository. The client carries the
publishable key; every Data API read sends the caller's token so RLS remains active.
The explicit owner filter on workspace reads adds another check. Child reads occur
only after the owned workspace is found. There is no elevated key or shared mutable
user session. Constructing a repository directly is for tests/internal code; never
use an owner ID supplied by an HTTP caller in place of this dependency.

Repository failures contain no upstream response text. Routes should translate:

| Failure | API behavior |
| --- | --- |
| `WorkspaceNotFound` | 404 for both absent and unowned workspaces |
| `UnsupportedDocumentType` | 409 `unsupported_document_type` |
| `DatabaseUnauthorized` | 401 with a Bearer challenge; the token may expire after Auth verification |
| `DatabaseUnavailable` | 503 with a safe `database_unavailable` detail; never echo upstream data |
| Invalid pagination (`ValueError`) | Validate query parameters in the route so invalid HTTP input receives 422 |

The auth dependency already handles missing/rejected tokens and Auth outages.
Database failures must not become empty lists, 404s or successful upload responses.
HTTP routes and their response schemas remain separate work for the API owner.

## Verification and remaining work

`tests/db/test_workspaces.py` uses synthetic HTTP responses to test request scoping,
ownership filters, parent resolution, pagination/counts, exact amounts, malformed
responses, dependency failures, and the real authentication dependency wiring.
These tests do not prove deployed RLS behavior; `supabase/tests/ownership.sql`
checks the actual database rules separately. Run a two-user API integration demo
once routes, parsers and upload persistence are connected.

Write repositories, private Storage helpers and atomic upload persistence are
upcoming work. No schema migration or hosted project change is required for these
reads. Do not introduce a generic repository framework.

Data API references: [pagination and exact counts](https://docs.postgrest.org/en/stable/references/api/pagination_count.html)
and [Supabase data security](https://supabase.com/docs/guides/database/secure-data).
