"""Fixtures for the API tests. pytest finds this file by name and shares its fixtures with every
test in this folder, no import needed.

The tests use a temporary SQLite file. To run them against Postgres instead (as deployed):
    TEST_DATABASE_URL=postgresql://... uv run pytest tests/api
"""

import os

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graph import build_graph
from app.api import auth, splits
from app.api.accounts import AccountStore
from app.api.claims import ClaimStore
from app.api.db import Database
from app.api.limits import RateLimit
from app.api.payments import PaymentStore
from app.api.photos import PhotoStore
from app.main import app
from tests.agent import fakes
from tests.api.helpers import fake_google


@pytest.fixture
def client(tmp_path, monkeypatch):
    """An API client whose agent uses the fakes, with its own temporary database, and a fake
    Google sign-in."""
    monkeypatch.setattr(auth.settings, "google_client_id", "test-client-id")
    graph = build_graph(
        InMemorySaver(), fakes.read_receipt, fakes.suggest_assignments, fakes.correct_assignments
    )
    database = Database(os.environ.get("TEST_DATABASE_URL", ""), sqlite_path=tmp_path / "test.db")
    payments = PaymentStore(database)
    accounts = AccountStore(database)
    photos = PhotoStore(database)
    app.dependency_overrides[splits.get_graph] = lambda: graph
    claims = ClaimStore(database)
    app.dependency_overrides[splits.get_payments] = lambda: payments
    app.dependency_overrides[splits.get_claims] = lambda: claims
    app.dependency_overrides[splits.get_photos] = lambda: photos
    split_limit = RateLimit(100, window_seconds=3600)  # each test starts with no splits counted
    app.dependency_overrides[splits.get_split_limit] = lambda: split_limit
    app.dependency_overrides[auth.get_accounts] = lambda: accounts
    app.dependency_overrides[auth.get_verifier] = lambda: fake_google
    yield TestClient(app)
    app.dependency_overrides.clear()
    if database.postgres:  # a shared database: leave it empty for the next test
        with database.connection() as connection:
            connection.execute("TRUNCATE payments, claims, photos, users, split_owners, friends")
        database.pool.close()
