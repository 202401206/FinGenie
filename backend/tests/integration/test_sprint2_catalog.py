"""Poison the disposable schema to prove the shared catalog audit catches regressions."""

from pathlib import Path

import pytest

from tests.integration.test_persistence_recovery import database as database

AUDIT = (
    Path(__file__).resolve().parents[3] / "supabase/tests/security_audit.sql"
).read_text(encoding="utf-8")
AUDIT_BLOCK = AUDIT[AUDIT.index("do $$") : AUDIT.index("$$;", AUDIT.index("do $$")) + 3]


@pytest.mark.parametrize(
    "mutation,restore,expected",
    [
        (
            "alter table public.upload_attempts disable row level security",
            "alter table public.upload_attempts enable row level security",
            "RLS missing",
        ),
        (
            "grant select on public.upload_attempts to anon",
            "revoke select on public.upload_attempts from anon",
            "anonymous",
        ),
        (
            "grant select(expected_json) on public.upload_attempts to anon",
            "revoke select(expected_json) on public.upload_attempts from anon",
            "anonymous",
        ),
        (
            "grant truncate on public.upload_attempts to authenticated",
            "revoke truncate on public.upload_attempts from authenticated",
            "TRUNCATE",
        ),
        (
            "grant execute on function public.begin_journal_recovery(uuid,bigint) to anon",
            "revoke execute on function public.begin_journal_recovery(uuid,bigint) from anon",
            "Anonymous function",
        ),
        (
            "alter function public.lock_financial_data() security definer",
            "alter function public.lock_financial_data() security invoker",
            "Unsafe invoker",
        ),
        (
            "alter function public.lock_financial_data() reset search_path",
            "alter function public.lock_financial_data() set search_path=''",
            "Unsafe invoker",
        ),
        (
            "grant update(expected_json) on public.upload_attempts to authenticated",
            "revoke update(expected_json) on public.upload_attempts from authenticated",
            "Immutable journal",
        ),
        (
            "update storage.buckets set public=true where id='financial-documents'",
            "update storage.buckets set public=false where id='financial-documents'",
            "bucket is public",
        ),
    ],
)
def test_catalog_audit_detects_security_regression_and_recovers(
    database, mutation, restore, expected
):
    assert "error" not in database(AUDIT_BLOCK)
    assert "error" not in database(mutation)
    try:
        result = database(AUDIT_BLOCK)
        assert result.get("error") == "P0001", result
        assert expected in result["message"]
    finally:
        assert "error" not in database(restore)
    assert "error" not in database(AUDIT_BLOCK)
