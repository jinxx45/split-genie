"""App settings, read from environment variables or from backend/.env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    gemini_api_key: str = ""  # empty until you add it to .env; tests don't need it


settings = Settings()
