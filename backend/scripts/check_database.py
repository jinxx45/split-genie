"""Check that every part of the app that stores data works on the configured database.

From the backend folder, after `neon deploy` has written the connection strings:
    uv run python -m scripts.check_database

Each check writes a test row, reads it back, and deletes it, so it's safe on a real database.
Never prints the connection string.
"""

import secrets
import sys
from urllib.parse import urlsplit

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command

from app.agent.graph import build_graph, new_split
from app.api.accounts import AccountStore
from app.api.claims import ClaimStore
from app.api.db import Database
from app.api.payments import PaymentStore
from app.api.photos import PhotoStore
from app.config import settings

TEST_RECEIPT = {
    "place": "Check",
    "items": [{"name": "Tea", "amount_paise": 2000, "category": "drink", "quantity": 1}],
    "tax_paise": 0,
    "service_charge_paise": 0,
    "printed_total_paise": 2000,
}


def main() -> None:
    database = Database(settings.database_url, settings.database_path)
    if database.postgres:
        host = urlsplit(settings.database_url).hostname or "?"
        print(f"Database: Postgres at {host}")
    else:
        print(f"Database: SQLite file {settings.database_path} (no DATABASE_URL found)")

    run_id = f"check-{secrets.token_hex(4)}"  # every test row is tagged with this
    checks = [
        ("connect", lambda: check_connect(database)),
        ("photos", lambda: check_photos(database, run_id)),
        ("payments", lambda: check_payments(database, run_id)),
        ("claims", lambda: check_claims(database, run_id)),
        ("accounts", lambda: check_accounts(database, run_id)),
        ("agent checkpoints", lambda: check_agent(database, run_id)),
    ]
    failed = False
    for name, check in checks:
        try:
            print(f"  ✓ {name}: {check()}")
        except Exception as error:  # report every check, not just the first failure
            failed = True
            print(f"  ✗ {name}: {type(error).__name__}: {error}")
    print("All checks passed." if not failed else "Some checks failed.")
    sys.exit(1 if failed else 0)


def check_connect(database: Database) -> str:
    with database.connection() as connection:
        row = connection.execute("SELECT 1 AS ok").fetchone()
    assert row["ok"] == 1
    return "query ran"


def check_photos(database: Database, run_id: str) -> str:
    photos = PhotoStore(database)
    photos.save(run_id, "image/jpeg", b"\xff\xd8\xff test")
    try:
        assert photos.load(run_id) == (b"\xff\xd8\xff test", "image/jpeg")
    finally:
        delete(database, "DELETE FROM photos WHERE id = ?", run_id)
    return "saved, read back, deleted"


def check_payments(database: Database, run_id: str) -> str:
    payments = PaymentStore(database)
    payments.mark_paid(run_id, "Arun", "Priya", "Arun")
    payments.mark_paid(run_id, "Arun", "Priya", "Priya")  # marking again updates the row
    assert payments.marked(run_id) == {("Arun", "Priya"): "Priya"}
    payments.mark_unpaid(run_id, "Arun", "Priya")
    assert payments.marked(run_id) == {}
    return "marked, updated, unmarked"


def check_claims(database: Database, run_id: str) -> str:
    claims = ClaimStore(database)
    claims.save(run_id, 0, "Arun", {0: 2})
    claims.save(run_id, 0, "Arun", {0: 1})  # a changed answer replaces the old one
    try:
        assert claims.claims(run_id, 0) == {"Arun": {0: 1}}
    finally:
        delete(database, "DELETE FROM claims WHERE split_id = ?", run_id)
    return "saved, replaced, read back, deleted"


def check_accounts(database: Database, run_id: str) -> str:
    accounts = AccountStore(database)
    try:
        user = accounts.sign_in(run_id, f"{run_id}@example.com", "Check")
        accounts.add_split(run_id, user.id)
        accounts.remember_friends(user.id, ["Arun"])
        accounts.set_friend_upi_id(user.id, "arun", "arun@oksbi")  # same friend, any case
        assert accounts.owner(run_id) == user.id
        assert [(f.name, f.upi_id) for f in accounts.friends(user.id)] == [("Arun", "arun@oksbi")]
    finally:
        delete(database, "DELETE FROM friends WHERE user_id = ?", run_id)
        delete(database, "DELETE FROM split_owners WHERE split_id = ?", run_id)
        delete(database, "DELETE FROM users WHERE id = ?", run_id)
    return "user, split owner and friend saved, read back, deleted"


def check_agent(database: Database, run_id: str) -> str:
    """Start a split, then open it again with a brand-new graph, as after a server restart."""
    if database.postgres:
        checkpointer = PostgresSaver(database.pool)
        checkpointer.setup()
    else:
        checkpointer = InMemorySaver()  # the SQLite path is covered by the test suite

    def build():  # no AI: the receipt and suggestions are fixed
        return build_graph(
            checkpointer,
            read_receipt=lambda receipt_id, feedback: TEST_RECEIPT,
            suggest_assignments=lambda people, note, items: {"suggestions": [], "light_eaters": []},
            correct_assignments=lambda people, items, note: {"corrections": [], "light_eaters": []},
        )

    config = {"configurable": {"thread_id": run_id}}
    try:
        build().invoke(new_split(["Arun", "Priya"], "", [run_id]), config)
        reopened = build()
        assert reopened.get_state(config).interrupts[0].value["step"] == "confirm_items"
        reopened.invoke(Command(resume=TEST_RECEIPT), config)
        assert reopened.get_state(config).interrupts[0].value["step"] == "review_assignments"
    finally:
        checkpointer.delete_thread(run_id)
    return "split saved, reopened by a fresh graph, answered, deleted"


def delete(database: Database, sql: str, value: str) -> None:
    with database.connection() as connection:
        connection.execute(sql, (value,))


if __name__ == "__main__":
    main()
