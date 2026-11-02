"""Receipt photos, kept in the database rather than on disk: a hosted app's disk can be wiped on
any restart, and the agent may need a photo again later (a retry after Gemini failed)."""

from app.api.db import Store, now


class PhotoStore(Store):
    SCHEMA = """
        CREATE TABLE IF NOT EXISTS photos (
            id TEXT PRIMARY KEY,
            content_type TEXT NOT NULL,
            data BYTEA NOT NULL,  -- the image bytes (SQLite stores them as they are)
            saved_at TEXT NOT NULL
        );
    """

    def save(self, photo_id: str, content_type: str, data: bytes) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO photos (id, content_type, data, saved_at) VALUES (?, ?, ?, ?)",
                (photo_id, content_type, data, now()),
            )

    def load(self, photo_id: str) -> tuple[bytes, str]:
        """(image bytes, content type), for the agent to send to Gemini."""
        with self.connection() as connection:
            row = connection.execute("SELECT content_type, data FROM photos WHERE id = ?", (photo_id,)).fetchone()
        if row is None:
            raise KeyError(f"No photo {photo_id}")
        return bytes(row["data"]), row["content_type"]
