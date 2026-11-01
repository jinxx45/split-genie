"""App settings, read from environment variables or from backend/.env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    gemini_api_key: str = ""  # empty until you add it to .env; tests don't need it
    gemini_model: str = "gemini-3.5-flash-lite"  # fast and low-cost; set GEMINI_MODEL to change
    uploads_dir: Path = Path("uploads")  # where receipt photos are saved
    database_path: Path = Path("split_genie.db")  # where splits are saved between requests
    log_level: str = "INFO"  # DEBUG also logs each step as it starts
    langsmith_api_key: str = ""  # set it to send traces to LangSmith; empty = off
    langsmith_project: str = "split-genie"


settings = Settings()
