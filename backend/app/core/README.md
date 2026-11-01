# Core - Backend team

`config.py` loads optional Supabase URL/publishable-key settings. `security.py`
provides `require_user`, which verifies bearer tokens with Supabase Auth and returns
only the user UUID. Reuse it with `Depends` on future protected routes. Each request
gets its own HTTP client; no user session is shared. Missing settings or upstream
failures produce sanitized 503 errors; invalid tokens produce 401. Health is public.
