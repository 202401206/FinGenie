# Settings API handoff

Implemented in the settings feature after persistence commit `da8b707`.
Apply the reviewed migrations, including
`20261117182410_user_settings_and_data_deletion.sql`, before using these routes
with a real Supabase project. This work has not deployed that migration.

## Authentication and base URL

`VITE_API_BASE_URL=http://localhost:8000/api` already includes `/api`. Append the
relative paths below once. Every request requires the signed-in user's access
token in `Authorization: Bearer <access_token>`. Do not send a user/owner ID.

Approved development origins remain localhost:5173 and 127.0.0.1:5173. CORS now
supports PATCH/DELETE and the optional Idempotency-Key header in addition to the
existing methods and headers.

## Account information

Supabase Auth remains the source of truth. Display `user.email` and
`user.user_metadata.full_name`. Update a name using
`supabase.auth.updateUser({ data: { full_name: newName } })`; update an email using
the supported Auth email flow and respect confirmation requirements. Handle the
returned error and update the shared Auth state after a successful change.

There is no separate profile record to synchronize and no new name/email FastAPI
endpoint. GET /api/me still returns only the verified UUID. A full name is display
metadata and must never determine authorization. No default-bank field is added.

## Preferences

| Method | Relative path | Success |
| --- | --- | --- |
| GET | `/me/preferences` | 200, full preferences object |
| PATCH | `/me/preferences` | 200, full saved preferences object |

```json
{"default_currency":"INR","theme":"light"}
```

- Currency values: INR, USD, EUR, GBP, AED, AUD, CAD, JPY.
- Theme values: light, dark.
- A missing preferences row returns INR/light without requiring setup. A database
  outage returns an error, not invented defaults.
- PATCH only the fields that changed. Omitted fields keep their saved value.
  An empty object is accepted and returns current/default preferences.
- Null, unknown fields, unsupported values and malformed requests return 422
  `invalid_preference`. Preferences are owned and persist across requests/devices.

Example using the existing API client:

```javascript
const preferences = await apiRequest('/me/preferences', { method: 'GET' });

const saved = await apiRequest('/me/preferences', {
  method: 'PATCH',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ theme: 'dark' }),
});
```

Load preferences when the authenticated account changes and keep them in shared
frontend state. Apply theme across the app. Ignore late responses from an old
account and do not reset preferences on an ordinary same-user token refresh.
Publish the saved response after success; if using optimistic UI, restore the
previous setting on failure.

**Currency rule:** a preference is not an exchange rate. Source/document currency
must label uploaded amounts and derived financial results. Changing a preference
from INR to USD must not turn INR 100 into USD 100. Null source currency stays
unknown. No source amounts, metadata, analysis units or parser support are changed
by these endpoints. In particular, preference values do not expand the initial
balance parser's INR/USD support. The frontend acceptance wording should follow
this rule rather than promising converted app-wide financial values.

## Delete financial data

After explicit user confirmation, call:

```http
DELETE /api/me/data
Authorization: Bearer <access_token>
Idempotency-Key: <UUID generated once for this confirmed deletion>
```

No request body is needed. The key is optional for compatibility, but the frontend
should generate it with `crypto.randomUUID()` before the first request and retain
it, scoped to the authenticated account, until this deletion is settled. It is a
request identifier, not an owner ID or credential. Do not generate a new key for
a retry of an unfinished deletion.

```javascript
// Create and retain this key only after the user confirms the destructive action.
const deletionKey = crypto.randomUUID();
await apiRequest('/me/data', {
  method: 'DELETE',
  headers: { 'Idempotency-Key': deletionKey },
});
```

Success is HTTP 200 with exactly:

```json
{"status":"deleted"}
```

Success means source removal was checked and owned transactions/documents/
workspaces were deleted. Bank and balance documents are included, as are owned
financial-bucket objects that have no remaining document row. Empty accounts also
succeed. The Auth account, name/email and preferences remain unchanged.

Current backend code does not persist chat history, reports or AI outputs in
separate tables. Their frontend state/caches still need clearing. Any future
workspace-linked persistent analysis/chat table or upload-attempt journal must be
integrated with deletion before it is enabled; do not retain financial payloads
in a second store. Minimal deletion receipts, generations and cancellation UUIDs
remain to prevent late writes and support retries. They contain no parsed JSON,
raw filenames, tokens or financial values. Source manifest paths are removed
after confirmed completion.

### Pending, errors and retry

Large deletions are bounded to 100 source objects per request. A deletion may need
another explicit call with the same key. There is no background worker or polling
completion promise. For example:

```json
{
  "detail": {
    "code": "data_deletion_pending",
    "message": "Deletion is incomplete. Retry this deletion with the same operation ID.",
    "operation_id": "<UUID>"
  }
}
```

| Status/code | Frontend action |
| --- | --- |
| 401 `unauthorized` | Reauthenticate the same account, then retry with the same key. Never sign into another account and replay its operation state. |
| 422 `invalid_preference` | Fix the preference request; do not show saved success. |
| 422 `invalid_request` | Fix the request/header, including a malformed UUID key. |
| 503 `settings_unavailable` | The database/Auth-dependent operation could not be confirmed. Keep the deletion key and retry the same request after recovery. Auth outages may instead return existing `auth_unavailable`. |
| 503 `data_deletion_pending` | Keep the pending UI and use the supplied operation_id as the same Idempotency-Key on the next explicit resume. |
| 409 `data_deletion_in_progress` | Another deletion key is already active. The user may explicitly resume that current deletion with a DELETE omitting the key; the server discovers their pending operation. Do not use this fallback for an outdated completed key. |
| 409 `deletion_request_outdated` | This key completed earlier and new data now exists. Do not reuse it or silently delete the new data. A fresh confirmation and new key are required. |
| 409 `data_deletion_conflict` | Current deletion state conflicts with the request; preserve state and show the error. |

An upload while deletion is pending returns 409 `data_deletion_in_progress`.
After completion, new uploads work normally. Replaying the completed deletion key
when no new data exists succeeds; replaying it after new uploads returns a conflict.
If a caller omits the key and no deletion is pending, DELETE starts a new deletion
of the account's current financial data. Use explicit keys for reliable retries.

Never show success for a timeout, network failure, pending result or unverified
removal. Storage/database operations cannot share one rollback. A partial failure
can leave some files deleted while database records remain pending; the same
operation resumes safely from persisted SQL progress without storing user tokens.

After success, invalidate outstanding financial requests and clear workspace,
transaction, drawer, chart, summary, chat and upload-result state/caches. Refresh
workspace lists. Preserve authentication and saved preferences. Also clear any
browser-persisted financial history owned by the same user.

## Internal upload integration note for Anshuman

`get_source_upload_access` now captures `upload_generation` after Auth verification
and before parsing/reservation. The existing UploadService copies it into the
internal SourceAttempt. Keep that value for the entire attempt. Balance upload
integration should use this same access object and copy the field too.

The reservation repository calls `reserve_source_upload_at_generation`; the older
seven-argument RPC remains generation-zero compatibility only. Do not fetch a new
generation midway through a failed old upload to make it pass. Deletion increments
the generation and invalidates pre-deletion attempts, even if they had not reserved
metadata yet. Existing registered attempts also receive cancellation markers.

Future durable recovery/journal work must preserve this generation and respect the
account-level deletion barrier. Do not replay or finalize deleted attempts using
fresh IDs, and do not leave expected financial JSON behind after deletion.

## Verification and deployment

Tests cover all preference values, partial updates, owner isolation, malformed
responses, browser preflight, deletion of bank/balance/orphan sources, preservation
of Auth/preferences, failure/resume, lost responses, bounded batches, rollback,
generation checks and newly uploaded data protection. PostgreSQL/RLS runs locally
in the embedded test harness; Auth/Storage HTTP is synthetic. Hosted Supabase,
independent database-session contention and browser end-to-end tests are separate
deployment checks. Run the new SQL suite only in a disposable test database.
