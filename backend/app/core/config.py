"""Settings shared by local development and Supabase authentication."""

from pydantic import AnyHttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FinGenie API"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    supabase_url: AnyHttpUrl | None = None
    supabase_publishable_key: SecretStr | None = None

    @field_validator("supabase_url", "supabase_publishable_key", mode="before")
    @classmethod
    def blank_is_unconfigured(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is None:
            return None
        if value.username or value.password or value.query or value.fragment:
            raise ValueError("Use only the Supabase project origin")
        if value.path not in (None, "", "/"):
            raise ValueError("Use the project URL without an API path")
        if value.scheme != "https" and value.host not in (
            "localhost",
            "127.0.0.1",
            "[::1]",
        ):
            raise ValueError("Supabase requires HTTPS except for local development")
        return value

    @field_validator("supabase_publishable_key")
    @classmethod
    def validate_publishable_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().startswith(
            "sb_publishable_"
        ):
            raise ValueError("Use a Supabase publishable key, not an elevated key")
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FINGENIE_",
        extra="ignore",
        hide_input_in_errors=True,
    )


settings = Settings()


def get_settings() -> Settings:
    """Dependency override point for tests; public health needs no Supabase config."""
    return settings
