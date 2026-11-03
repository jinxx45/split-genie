"""Where the app's own tables live (payments, accounts, claims, photos): a SQLite file on your
laptop, or Postgres when DATABASE_URL is set (the deployed app, whose disk is wiped on restart).

Queries are written once, with ? placeholders and SQL both databases understand.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings


@lru_cache  # one for the whole app; tests make their own
def get_database() -> "Database":
    return Database(settings.database_url, settings.database_path)


class Database:
    def __init__(self, url: str = "", sqlite_path: Path = Path("split_genie.db")):
        self.postgres = url.startswith(("postgres://", "postgresql://"))
        self.sqlite_path = sqlite_path
        self.pool: ConnectionPool | None = None
        if self.postgres:
            # A few connections, opened once and reused: a new connection to a hosted database
            # costs a network round trip and a TLS handshake. These settings are also what
            # LangGraph's Postgres checkpointer needs, so it shares the pool.
            self.pool = ConnectionPool(
                url,
                min_size=1,
                max_size=5,
                kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
                open=True,
            )

    @contextmanager
    def connection(self) -> Iterator["Connection"]:
        if self.pool is not None:
            with self.pool.connection() as raw:
                yield Connection(raw, postgres=True)
            return
        raw = sqlite3.connect(self.sqlite_path)
        raw.row_factory = sqlite3.Row  # rows can be read by column name: row["email"]
        try:
            with raw:  # commits if the block succeeds, rolls back if it raises
                yield Connection(raw, postgres=False)
        finally:
            raw.close()


class Connection:
    """A connection that takes ? placeholders on either database."""

    def __init__(self, raw: Any, postgres: bool):
        self.raw = raw
        self.postgres = postgres

    def execute(self, sql: str, params: tuple = ()) -> Any:
        if self.postgres:
            sql = sql.replace("?", "%s")  # psycopg's placeholder; our SQL never contains a literal ?
        return self.raw.execute(sql, params)


class Store:
    """The base for a group of tables. SCHEMA: CREATE TABLE IF NOT EXISTS statements, run on start.
    Statements are split at each semicolon, so comments in SCHEMA must not contain one."""

    SCHEMA = ""

    def __init__(self, database: Database):
        self.database = database
        with self.connection() as connection:
            for statement in self.SCHEMA.split(";"):
                if statement.strip():
                    connection.execute(statement)

    def connection(self):
        return self.database.connection()


def now() -> str:
    """The time in UTC, e.g. "2026-11-02T09:14:05.123456Z". Set in Python, not by the database, so
    both databases store it the same way. Sorts correctly as text, to the microsecond, so rows
    saved one after another keep their order."""
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
