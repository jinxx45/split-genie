"""App settings, read from environment variables or from backend/.env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    gemini_api_key: str = ""  # empty until you add it to .env; tests don't need it
    gemini_model: str = "gemini-3.5-flash-lite"  # fast and low-cost; set GEMINI_MODEL to change
    uploads_dir: Path = Path("uploads")  # where receipt photos are saved
    database_path: Path = Path("split_genie.db")  # where splits are saved between requests (SQLite)
    max_splits_per_hour: int = 20  # per visitor (IP address): each split reads a bill with Gemini
    database_url: str = ""
    frontend_dir: Path = Path("static")  # the built React app; served at / when the folder exists  # a Postgres URL (the deployed app) is used instead of the SQLite file
    log_level: str = "INFO"  # DEBUG also logs each step as it starts
    langsmith_api_key: str = ""  # set it to send traces to LangSmith; empty = off
    langsmith_project: str = "split-genie"
    google_client_id: str = ""  # from Google Cloud: turns on "Sign in with Google"; empty = off
    session_secret: str = ""  # signs the sign-in cookie; empty = a new one each start (dev only)


settings = Settings()
