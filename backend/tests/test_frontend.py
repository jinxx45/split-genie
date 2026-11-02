"""Serving the built React app from FastAPI (the deployed setup)."""

import importlib

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>the app</html>")
    (tmp_path / "assets" / "app-1234.js").write_text("console.log('hi')")
    (tmp_path.parent / "secret.txt").write_text("not for you")
    monkeypatch.setattr(settings, "frontend_dir", tmp_path)
    yield TestClient(importlib.reload(main).app)  # re-run main.py so it sees the folder
    monkeypatch.undo()
    importlib.reload(main)


def test_any_app_address_gets_the_app_page(client):
    for path in ("/", "/split/abc123", "/split/abc123?who"):
        response = client.get(path)
        assert response.status_code == 200 and "the app" in response.text


def test_built_files_are_served_and_cached(client):
    response = client.get("/assets/app-1234.js")

    assert response.text == "console.log('hi')"
    assert "immutable" in response.headers["cache-control"]


def test_api_still_works_and_unknown_api_addresses_are_404(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/nope").status_code == 404


def test_files_outside_the_folder_are_never_served(client):
    response = client.get("/..%2Fsecret.txt")

    assert "not for you" not in response.text
