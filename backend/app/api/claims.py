"""What friends say they had, while the split waits on "who had what".

Each friend's answer for a receipt is one row: {item index: weight}. An empty answer is still an
answer ("I had none of this"), so the splitter can see who has replied.
"""

import json

from app.api.db import SqliteStore


class ClaimStore(SqliteStore):
    SCHEMA = """
        CREATE TABLE IF NOT EXISTS claims (
            split_id TEXT NOT NULL,
            receipt INTEGER NOT NULL,
            person TEXT NOT NULL,
            items TEXT NOT NULL,  -- JSON: {"item index": weight}
            answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (split_id, receipt, person)
        );
    """

    def claims(self, split_id: str, receipt: int) -> dict[str, dict[int, int]]:
        """person -> {item index: weight}, for everyone who has answered for this receipt."""
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT person, items FROM claims WHERE split_id = ? AND receipt = ? ORDER BY answered_at, rowid",
                (split_id, receipt),
            )
            return {
                row["person"]: {int(index): weight for index, weight in json.loads(row["items"]).items()}
                for row in rows
            }

    def save(self, split_id: str, receipt: int, person: str, items: dict[int, int]) -> None:
        """Save a friend's answer, replacing any earlier one."""
        with self.connection() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO claims (split_id, receipt, person, items) VALUES (?, ?, ?, ?)",
                (split_id, receipt, person, json.dumps(items)),
            )
