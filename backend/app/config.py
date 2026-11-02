"""App settings, read from environment variables, backend/.env, and the repo root's .env.local
(where `neon deploy` writes the database's connection strings)."""

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Later files win, so Neon's values in .env.local take priority. Missing files are skipped.
    model_config = SettingsConfigDict(env_file=(".env", "../.env.local"), extra="ignore")

    gemini_api_key: str = ""  # empty until you add it to .env; tests don't need it
    gemini_model: str = "gemini-3.5-flash-lite"  # fast and low-cost; set GEMINI_MODEL to change
    uploads_dir: Path = Path("uploads")  # where receipt photos are saved
    database_path: Path = Path("split_genie.db")  # where splits are saved between requests (SQLite)
    max_splits_per_hour: int = 20  # per visitor (IP address): each split reads a bill with Gemini
    # A Postgres URL is used instead of the SQLite file. Neon gives two: the direct one
    # (DATABASE_URL_UNPOOLED) is preferred, because the app creates its tables at startup, which
    # Neon's pooled connection doesn't support, and keeps its own small pool of connections.
    database_url: str = Field("", validation_alias=AliasChoices("DATABASE_URL_UNPOOLED", "DATABASE_URL"))
    frontend_dir: Path = Path("static")  # the built React app; served at / when the folder exists
    log_level: str = "INFO"  # DEBUG also logs each step as it starts
    langsmith_api_key: str = ""  # set it to send traces to LangSmith; empty = off
    langsmith_project: str = "split-genie"
    google_client_id: str = ""  # from Google Cloud: turns on "Sign in with Google"; empty = off
    session_secret: str = ""  # signs the sign-in cookie; empty = a new one each start (dev only)


settings = Settings()
