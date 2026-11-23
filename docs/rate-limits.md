# Request limits

The API limits expensive authenticated attempts by the UUID returned by verified
Supabase Auth. Summary and chat share one AI allowance across all workspaces and
access tokens for that user. Uploads have a separate allowance. IP headers,
request-selected owner IDs and unverified JWT claims do not select the counter.

| Environment setting | Default | Meaning |
| --- | --- | --- |
| `FINGENIE_RATE_LIMIT_AI_REQUESTS` | 10 | Combined summary/chat attempts per window |
| `FINGENIE_RATE_LIMIT_UPLOAD_REQUESTS` | 5 | Upload attempts per window |
| `FINGENIE_RATE_LIMIT_WINDOW_SECONDS` | 60 | Window duration, in seconds |
| `FINGENIE_RATE_LIMIT_MAX_BUCKETS` | 10000 | Maximum active user/request-group counters per API process |

Settings must be positive whole numbers. Request limits are capped at 10,000,
window duration at 86,400 seconds, and bucket capacity at 100,000. Restart the API
after changing settings. See `backend/.env.example`.

A user's first allowed attempt starts that group's fixed window. At most the
configured number of attempts is admitted before the window expires. Attempts
that subsequently fail validation, ownership, parsing or a provider request still
count. A denied attempt does not extend the window or trigger automatic retries.
Fixed windows allow adjacent-window bursts; this is not a sliding-window quota.

Auth verification runs first. Rejected/missing credentials and Auth outages do not
consume an allowance. Rejection occurs before upload access, multipart parsing,
source writes and AI/provider execution. FastAPI reuses the verified Auth
dependency within the request. Unauthenticated traffic still reaches Auth when a
token is supplied; this feature is not an infrastructure-level flood defence.

Health, workspace/analysis reads, identity, Settings, manual recovery and CORS
preflight do not consume these allowances. Adding another expensive endpoint
requires deliberately assigning it to a group.

## Responses and frontend handling

An exhausted allowance returns HTTP 429:

```json
{
  "detail": {
    "code": "rate_limit_exceeded",
    "message": "Too many AI requests. Please retry later."
  }
}
```

`Retry-After` is a positive integer number of seconds until the original window
expires, rounded up. The existing error envelope stays unchanged. CORS exposes
the header to approved browser origins. Show a wait/retry state; do not replay an
upload automatically or assume this means an earlier uncertain upload failed.
Upstream AI-provider 429 errors retain their existing handling and may not carry
the application's Retry-After header.

Expired counters are removed. If capacity is exhausted by active counters, a new
user/group receives HTTP 503 `rate_limit_unavailable` with Retry-After until the
earliest tracked window expires. Existing counters remain enforced; the API does
not evict an active user to grant a fresh allowance. No parsed data or tokens are
stored in the counter.

## Deployment boundary

This implementation is an in-memory, thread-safe limiter for **one API worker in
one running instance**. Counters reset on server restart. Separate workers or
replicas do not share counters, so do not claim a global quota when running more
than one. Before scaling, replace the counter store with a shared atomic store
and test cross-worker enforcement. No Redis service, database schema or hosted
Supabase change is introduced by this commit.

## Integration and checks

Limits are attached in `backend/app/api/router.py` while registering the AI and
upload routers. Preserve both dependencies when merging later API/dashboard work.
Individual handlers, ownership policy, save receipts and recovery are unchanged.
The application lifespan creates fresh process-local state for the running app.

Focused verification from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_rate_limit_store.py tests/api/test_rate_limits.py
```

Tests exercise concurrent admission, exact window boundaries, token refresh,
user/group isolation, spoofed headers, early upload rejection, safe capacity
failure, Auth failures, read/preflight behavior and browser-visible retry headers.
