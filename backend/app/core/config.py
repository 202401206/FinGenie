"""Local settings. No Supabase or LLM credentials are required to start."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FinGenie API"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

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
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton for dependency injection."""
    return Settings()


settings = get_settings()
