"""People who sign in, the splits they started, and the friends they split with.

Signing in is optional. A split started while signed in has an owner: only they can answer its
questions, and it shows in their history. Friends (with their UPI IDs) are remembered per user
so they can be added with a tap next time.
"""

from dataclasses import dataclass

from app.api.db import SqliteStore


@dataclass
class User:
    id: str  # Google's id for the account ("sub"); never changes, unlike the email
    email: str
    name: str  # first name, used as their name in splits
    upi_id: str


@dataclass
class Friend:
    name: str
    upi_id: str


class AccountStore(SqliteStore):
    SCHEMA = """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            name TEXT NOT NULL,
            upi_id TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS split_owners (
            split_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS friends (
            user_id TEXT NOT NULL,
            name TEXT NOT NULL COLLATE NOCASE,  -- "priya" and "Priya" are the same friend
            upi_id TEXT NOT NULL DEFAULT '',
            last_split_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, name)
        );
    """

    # --- Users ---

    def sign_in(self, user_id: str, email: str, name: str) -> User:
        """Create the user on first sign-in; afterwards keep their details up to date."""
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO users (id, email, name) VALUES (?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET email = excluded.email, name = excluded.name
                """,
                (user_id, email, name),
            )
        return self.user(user_id)

    def user(self, user_id: str) -> User | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return User(**row) if row else None

    def set_upi_id(self, user_id: str, upi_id: str) -> None:
        with self.connection() as connection:
            connection.execute("UPDATE users SET upi_id = ? WHERE id = ?", (upi_id, user_id))

    # --- Splits ---

    def add_split(self, split_id: str, user_id: str) -> None:
        with self.connection() as connection:
            connection.execute("INSERT INTO split_owners (split_id, user_id) VALUES (?, ?)", (split_id, user_id))

    def owner(self, split_id: str) -> str | None:
        """The id of the user who started the split; None if it was started without signing in."""
        with self.connection() as connection:
            row = connection.execute("SELECT user_id FROM split_owners WHERE split_id = ?", (split_id,)).fetchone()
        return row["user_id"] if row else None

    def splits(self, user_id: str) -> list[tuple[str, str]]:
        """(split id, when it was started) for the user's splits, newest first."""
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT split_id, created_at FROM split_owners WHERE user_id = ? ORDER BY created_at DESC, rowid DESC",
                (user_id,),
            )
            return [(row["split_id"], row["created_at"]) for row in rows]

    # --- Friends ---

    def friends(self, user_id: str) -> list[Friend]:
        """Everyone the user has split with, most recent first."""
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT name, upi_id FROM friends WHERE user_id = ? ORDER BY last_split_at DESC, rowid DESC",
                (user_id,),
            )
            return [Friend(**row) for row in rows]

    def remember_friends(self, user_id: str, names: list[str]) -> None:
        """Save new friends, and move ones split with again to the top of the list."""
        with self.connection() as connection:
            connection.executemany(
                """
                INSERT INTO friends (user_id, name) VALUES (?, ?)
                ON CONFLICT (user_id, name) DO UPDATE SET last_split_at = CURRENT_TIMESTAMP
                """,
                [(user_id, name) for name in names],
            )

    def set_friend_upi_id(self, user_id: str, name: str, upi_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO friends (user_id, name, upi_id) VALUES (?, ?, ?)
                ON CONFLICT (user_id, name) DO UPDATE SET upi_id = excluded.upi_id
                """,
                (user_id, name, upi_id),
            )
