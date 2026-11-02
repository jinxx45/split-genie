"""The base for the app's own SQLite tables (payments, accounts). The agent keeps its own
checkpoint tables in the same file."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class SqliteStore:
    SCHEMA = ""  # CREATE TABLE IF NOT EXISTS ... statements, run once on start

    def __init__(self, path: Path):
        self.path = path
        with self.connection() as connection:
            connection.executescript(self.SCHEMA)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """A short-lived connection per call, so requests on different threads never share one.
        Commits if the block succeeds, rolls back if it raises."""
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row  # rows can be read by column name: row["email"]
        try:
            with connection:
                yield connection
        finally:
            connection.close()
