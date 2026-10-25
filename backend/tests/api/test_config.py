import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_blank_supabase_settings_are_optional(monkeypatch):
    monkeypatch.setenv("FINGENIE_SUPABASE_URL", "")
    monkeypatch.setenv("FINGENIE_SUPABASE_PUBLISHABLE_KEY", "")
    config = Settings(_env_file=None)
    assert config.supabase_url is None
    assert config.supabase_publishable_key is None


@pytest.mark.parametrize(
    "url",
    [
        "http://example.test",
        "https://user:password@example.test",
        "https://example.test/auth/v1",
        "https://example.test?token=private",
        "https://example.test/#fragment",
    ],
)
def test_only_project_origins_are_accepted(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, supabase_url=url)


@pytest.mark.parametrize("key", ["sb_secret_private", "legacy-or-arbitrary-token"])
def test_elevated_or_unrecognized_keys_are_rejected(key):
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, supabase_publishable_key=key)
    assert key not in str(error.value)


def test_key_is_redacted_and_local_supabase_is_supported():
    config = Settings(
        _env_file=None,
        supabase_url="http://127.0.0.1:54321",
        supabase_publishable_key="sb_publishable_synthetic",
    )
    assert "sb_publishable_synthetic" not in repr(config)
