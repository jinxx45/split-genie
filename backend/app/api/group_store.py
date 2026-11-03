"""Groups (Friends, Trip, Flatmates) and their running tab: expenses, repayments and, for
flatmates, monthly recurring bills.

Lists and maps (members, who paid, who owes) are stored as JSON text, which both SQLite and
Postgres handle the same way.
"""

import json
import secrets
from dataclasses import dataclass
from typing import Literal

from app.api.db import Store, now

GroupKind = Literal["friends", "trip", "flat"]


@dataclass
class Group:
    id: str
    kind: GroupKind
    name: str
    members: list[str]
    owner_id: str  # the signed-in user who created it
    upi_ids: dict[str, str]  # member -> UPI ID, for pay buttons
    start_date: str | None  # trips: "2026-12-12"
    end_date: str | None
    closed_at: str | None  # trips: set when the trip is ended; no new expenses after that
    created_at: str


@dataclass
class ExpenseRow:
    id: str
    title: str
    source: Literal["bill", "quick", "recurring"]  # a scanned bill, a quick expense, or a monthly bill
    paid: dict[str, int]
    owed: dict[str, int]
    added_by: str  # the member who added it ("" for automatic ones)
    created_at: str
    split_id: str | None  # the scanned bill's split
    recurring_id: str | None  # the monthly bill it came from
    month: str | None  # for monthly bills: "2026-11"


@dataclass
class RepaymentRow:
    id: str
    sender: str
    receiver: str
    amount_paise: int
    marked_by: str
    created_at: str


@dataclass
class RecurringRow:
    """A flatmates' monthly bill. A fixed amount (rent) is added on its own every month; with no
    amount (electricity), the payer is asked for each month's figure."""

    id: str
    title: str
    amount_paise: int | None  # None: the amount changes each month
    paid_by: str
    weights: dict[str, int]  # how it's shared, e.g. a bigger room pays 2 shares
    day_of_month: int  # when it's due, 1 to 28
    starts: str  # first month it applies to: "2026-11"
    stopped_at: str | None


def new_id() -> str:
    return secrets.token_urlsafe(9)  # unguessable: a group's link is how members get in


class GroupStore(Store):
    SCHEMA = """
        CREATE TABLE IF NOT EXISTS groups (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            members TEXT NOT NULL,  -- JSON list of names
            owner_id TEXT NOT NULL,
            upi_ids TEXT NOT NULL,  -- JSON {member: UPI ID}
            start_date TEXT,
            end_date TEXT,
            closed_at TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS group_users (
            group_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            member TEXT NOT NULL,  -- which member of the group this account is
            PRIMARY KEY (group_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id TEXT PRIMARY KEY,
            group_id TEXT NOT NULL,
            title TEXT NOT NULL,
            source TEXT NOT NULL,
            paid TEXT NOT NULL,  -- JSON {member: paise}
            owed TEXT NOT NULL,  -- JSON {member: paise}
            added_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            split_id TEXT,
            recurring_id TEXT,
            month TEXT
        );
        CREATE INDEX IF NOT EXISTS expenses_by_group ON expenses (group_id);
        -- A scanned bill is added only once, and a monthly bill once per month (NULLs never clash).
        CREATE UNIQUE INDEX IF NOT EXISTS expenses_one_per_split ON expenses (split_id);
        CREATE UNIQUE INDEX IF NOT EXISTS expenses_one_per_month ON expenses (recurring_id, month);
        CREATE TABLE IF NOT EXISTS repayments (
            id TEXT PRIMARY KEY,
            group_id TEXT NOT NULL,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            amount_paise INTEGER NOT NULL,
            marked_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS repayments_by_group ON repayments (group_id);
        CREATE TABLE IF NOT EXISTS recurring (
            id TEXT PRIMARY KEY,
            group_id TEXT NOT NULL,
            title TEXT NOT NULL,
            amount_paise INTEGER,
            paid_by TEXT NOT NULL,
            weights TEXT NOT NULL,  -- JSON {member: weight}
            day_of_month INTEGER NOT NULL,
            starts TEXT NOT NULL,
            stopped_at TEXT,
            created_at TEXT NOT NULL
        );
    """

    # --- Groups ---

    def create(
        self,
        kind: GroupKind,
        name: str,
        members: list[str],
        owner_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        group_id = new_id()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO groups (id, kind, name, members, owner_id, upi_ids, start_date, end_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (group_id, kind, name, json.dumps(members), owner_id, "{}", start_date, end_date, now()),
            )
        return group_id

    def group(self, group_id: str) -> Group | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
        if row is None:
            return None
        values = dict(row)
        values["members"] = json.loads(values["members"])
        values["upi_ids"] = json.loads(values["upi_ids"])
        return Group(**values)

    def set_upi_id(self, group_id: str, member: str, upi_id: str) -> None:
        group = self.group(group_id)
        upi_ids = {**group.upi_ids, member: upi_id}
        with self.connection() as connection:
            connection.execute("UPDATE groups SET upi_ids = ? WHERE id = ?", (json.dumps(upi_ids), group_id))

    def set_closed(self, group_id: str, closed: bool) -> None:
        with self.connection() as connection:
            connection.execute("UPDATE groups SET closed_at = ? WHERE id = ?", (now() if closed else None, group_id))

    # --- Which accounts belong to which groups ---

    def join(self, group_id: str, user_id: str, member: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO group_users (group_id, user_id, member) VALUES (?, ?, ?)
                ON CONFLICT (group_id, user_id) DO UPDATE SET member = excluded.member
                """,
                (group_id, user_id, member),
            )

    def groups_of(self, user_id: str) -> list[tuple[Group, str]]:
        """(group, which member the user is in it), newest group first."""
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT g.id, u.member FROM groups g JOIN group_users u ON u.group_id = g.id
                WHERE u.user_id = ? ORDER BY g.created_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [(self.group(row["id"]), row["member"]) for row in rows]

    # --- Expenses ---

    def add_expense(
        self,
        group_id: str,
        title: str,
        source: str,
        paid: dict[str, int],
        owed: dict[str, int],
        added_by: str,
        split_id: str | None = None,
        recurring_id: str | None = None,
        month: str | None = None,
    ) -> None:
        """Add an expense. Adding the same scanned bill, or the same month of a monthly bill,
        twice does nothing the second time."""
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO expenses
                    (id, group_id, title, source, paid, owed, added_by, created_at, split_id, recurring_id, month)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    new_id(), group_id, title, source, json.dumps(paid), json.dumps(owed), added_by, now(),
                    split_id, recurring_id, month,
                ),
            )

    def expenses(self, group_id: str) -> list[ExpenseRow]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM expenses WHERE group_id = ? ORDER BY created_at", (group_id,)
            ).fetchall()
        result = []
        for row in rows:
            values = {key: row[key] for key in ExpenseRow.__dataclass_fields__}
            values["paid"] = json.loads(values["paid"])
            values["owed"] = json.loads(values["owed"])
            result.append(ExpenseRow(**values))
        return result

    def delete_expense(self, group_id: str, expense_id: str) -> bool:
        with self.connection() as connection:
            cursor = connection.execute("DELETE FROM expenses WHERE id = ? AND group_id = ?", (expense_id, group_id))
            return cursor.rowcount > 0

    # --- Repayments ---

    def add_repayment(self, group_id: str, sender: str, receiver: str, amount_paise: int, marked_by: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO repayments (id, group_id, sender, receiver, amount_paise, marked_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (new_id(), group_id, sender, receiver, amount_paise, marked_by, now()),
            )

    def repayments(self, group_id: str) -> list[RepaymentRow]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM repayments WHERE group_id = ? ORDER BY created_at", (group_id,)
            ).fetchall()
        return [RepaymentRow(**{key: row[key] for key in RepaymentRow.__dataclass_fields__}) for row in rows]

    def delete_repayment(self, group_id: str, repayment_id: str) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                "DELETE FROM repayments WHERE id = ? AND group_id = ?", (repayment_id, group_id)
            )
            return cursor.rowcount > 0

    # --- Monthly bills (flatmates) ---

    def add_recurring(
        self,
        group_id: str,
        title: str,
        amount_paise: int | None,
        paid_by: str,
        weights: dict[str, int],
        day_of_month: int,
        starts: str,
    ) -> str:
        recurring_id = new_id()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO recurring
                    (id, group_id, title, amount_paise, paid_by, weights, day_of_month, starts, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (recurring_id, group_id, title, amount_paise, paid_by, json.dumps(weights), day_of_month, starts, now()),
            )
        return recurring_id

    def recurring(self, group_id: str) -> list[RecurringRow]:
        """The group's monthly bills that haven't been stopped, oldest first."""
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM recurring WHERE group_id = ? AND stopped_at IS NULL ORDER BY created_at", (group_id,)
            ).fetchall()
        result = []
        for row in rows:
            values = {key: row[key] for key in RecurringRow.__dataclass_fields__}
            values["weights"] = json.loads(values["weights"])
            result.append(RecurringRow(**values))
        return result

    def stop_recurring(self, group_id: str, recurring_id: str) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                "UPDATE recurring SET stopped_at = ? WHERE id = ? AND group_id = ? AND stopped_at IS NULL",
                (now(), recurring_id, group_id),
            )
            return cursor.rowcount > 0
