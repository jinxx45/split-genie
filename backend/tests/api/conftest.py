"""Fixtures for the API tests. pytest finds this file by name and shares its fixtures with every
test in this folder, no import needed."""

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graph import build_graph
from app.api import auth, splits
from app.api.accounts import AccountStore
from app.api.payments import PaymentStore
from app.main import app
from tests.agent import fakes
from tests.api.helpers import fake_google


@pytest.fixture
def client(tmp_path, monkeypatch):
    """An API client whose agent uses the fakes, with its own temporary database, and a fake
    Google sign-in."""
    monkeypatch.setattr(splits.settings, "uploads_dir", tmp_path / "uploads")
    monkeypatch.setattr(auth.settings, "google_client_id", "test-client-id")
    graph = build_graph(
        InMemorySaver(), fakes.read_receipt, fakes.suggest_assignments, fakes.correct_assignments
    )
    payments = PaymentStore(tmp_path / "test.db")
    accounts = AccountStore(tmp_path / "test.db")
    app.dependency_overrides[splits.get_graph] = lambda: graph
    app.dependency_overrides[splits.get_payments] = lambda: payments
    app.dependency_overrides[auth.get_accounts] = lambda: accounts
    app.dependency_overrides[auth.get_verifier] = lambda: fake_google
    yield TestClient(app)
    app.dependency_overrides.clear()
