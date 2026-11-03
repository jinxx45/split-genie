from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "split-genie"}


def test_site_details_include_the_contact_email(monkeypatch):
    monkeypatch.setattr(settings, "contact_email", "hello@example.com")

    assert TestClient(app).get("/api/site").json() == {"contact_email": "hello@example.com"}
