"""Local settings. No Supabase or LLM credentials are required to start."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FinGenie API"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FINGENIE_",
        extra="ignore",
    )


settings = Settings()
