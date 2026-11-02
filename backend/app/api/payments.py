"""Who has paid, for finished splits.

Kept outside the agent: by the time people pay, the split itself is finished. A row means the
payment was marked as paid (by the payer, or by the person being paid); no row means waiting.
"""

from app.api.db import SqliteStore


class PaymentStore(SqliteStore):
    SCHEMA = """
        CREATE TABLE IF NOT EXISTS payments (
            split_id TEXT NOT NULL,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            marked_by TEXT NOT NULL,
            marked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (split_id, sender, receiver)
        );
    """

    def marked(self, split_id: str) -> dict[tuple[str, str], str]:
        """(sender, receiver) -> who marked it paid, for every paid payment in the split."""
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT sender, receiver, marked_by FROM payments WHERE split_id = ?", (split_id,)
            )
            return {(row["sender"], row["receiver"]): row["marked_by"] for row in rows}

    def mark_paid(self, split_id: str, sender: str, receiver: str, marked_by: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO payments (split_id, sender, receiver, marked_by) VALUES (?, ?, ?, ?)",
                (split_id, sender, receiver, marked_by),
            )

    def mark_unpaid(self, split_id: str, sender: str, receiver: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "DELETE FROM payments WHERE split_id = ? AND sender = ? AND receiver = ?",
                (split_id, sender, receiver),
            )
