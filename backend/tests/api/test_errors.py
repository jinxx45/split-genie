"""Every error reaches the app as JSON with a sentence it can show, and crashes are logged in full."""

import logging

from fastapi.testclient import TestClient

from app.api import splits
from app.main import app


def broken_graph():
    raise RuntimeError("a bug")


def test_a_crash_returns_json_with_a_reference_and_logs_the_traceback(caplog):
    app.dependency_overrides[splits.get_graph] = broken_graph
    try:
        with caplog.at_level(logging.ERROR, logger="split_genie.api"):
            response = TestClient(app).get("/api/splits/abc")
    finally:
        app.dependency_overrides.clear()

    request_id = response.headers["X-Request-ID"]
    assert response.status_code == 500
    assert response.json() == {"detail": f"Something went wrong on our side (ref {request_id}). Please try again."}
    failure = next(record for record in caplog.records if record.getMessage().startswith("request failed"))
    assert f"id={request_id}" in failure.getMessage()
    assert failure.exc_info is not None  # the traceback is in the log


def test_validation_errors_are_one_readable_sentence(client):
    response = client.post("/api/splits", data={"note": "x"}, files=[])

    assert response.status_code == 422
    assert response.json() == {"detail": "name: Field required"}
