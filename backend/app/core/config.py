"""Settings shared by local development, Supabase authentication, and AI services."""

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

    # --- Groq LLM Configuration ---
    # SecretStr protects the API key from leaking into server logs or traceback prints
    groq_api_key: SecretStr | None = None
    # Default model on Groq: high-reasoning model with native tool calling
    groq_model: str = "openai/gpt-oss-120b"
    # Base URL for Groq's OpenAI-compatible chat completions API
    groq_base_url: str = "https://api.groq.com/openai/v1"

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
