import logging
import os

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app import observability
from app.agent.graph import build_graph, new_split
from app.main import app
from app.observability import AgentLogHandler, enable_langsmith_if_configured
from tests.agent import fakes

PEOPLE = ["Arun", "Priya"]
NOTE = "Priya skipped the coffee"


def run_until_first_pause(read_receipt=fakes.read_receipt):
    graph = build_graph(
        InMemorySaver(), read_receipt, fakes.suggest_assignments, fakes.correct_assignments
    )
    graph.invoke(
        new_split(PEOPLE, NOTE, ["lunch"], "Lunch"), {"configurable": {"thread_id": "split-42"}}
    )


def test_each_step_is_logged_with_its_split_and_duration(caplog):
    caplog.set_level(logging.DEBUG)

    run_until_first_pause()

    lines = [record.getMessage() for record in caplog.records if record.name == "split_genie.agent"]
    assert any(
        line.startswith("node finished split=split-42 node=extract_items ms=") for line in lines
    )
    assert "node paused for the user split=split-42 node=confirm_items" in lines
    assert not any("failed" in line for line in lines)  # a pause is not an error


def test_logs_never_contain_names_or_notes(caplog):
    caplog.set_level(logging.DEBUG)

    run_until_first_pause()

    everything = " ".join(record.getMessage() for record in caplog.records)
    for private in [*PEOPLE, NOTE, "Meals"]:
        assert private not in everything


def test_a_failing_step_is_logged_as_an_error(caplog):
    def broken_reader(receipt_id, feedback):
        raise RuntimeError("Gemini is down")

    with pytest.raises(RuntimeError):
        run_until_first_pause(read_receipt=broken_reader)

    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert "node failed split=split-42 node=extract_items" in errors[0]
    assert "error=RuntimeError" in errors[0]
    assert "Gemini is down" not in errors[0]  # error messages can hold data; only the type is logged


def test_llm_calls_are_logged_with_tokens(caplog):
    caplog.set_level(logging.INFO)
    model = GenericFakeChatModel(
        messages=iter(
            [
                AIMessage(
                    content="ok",
                    usage_metadata={"input_tokens": 812, "output_tokens": 64, "total_tokens": 876},
                )
            ]
        )
    )

    model.invoke("hello", config={"callbacks": [AgentLogHandler()]})

    line = next(r.getMessage() for r in caplog.records if r.name == "split_genie.llm")
    assert line.startswith("llm call finished")
    assert "input_tokens=812 output_tokens=64" in line


client = TestClient(app)


def test_requests_are_logged_and_get_a_request_id(caplog):
    caplog.set_level(logging.INFO)

    response = client.get("/api/health")

    request_id = response.headers["X-Request-ID"]
    line = next(r.getMessage() for r in caplog.records if r.name == "split_genie.api")
    assert line.startswith(f"request id={request_id} method=GET path=/api/health status=200 ms=")


def test_a_safe_request_id_from_the_browser_is_kept_and_an_unsafe_one_replaced():
    kept = client.get("/api/health", headers={"X-Request-ID": "abc-123"})
    replaced = client.get("/api/health", headers={"X-Request-ID": "x\nFAKE LOG LINE"})

    assert kept.headers["X-Request-ID"] == "abc-123"
    assert "FAKE" not in replaced.headers["X-Request-ID"]


def test_langsmith_stays_off_without_a_key(monkeypatch):
    monkeypatch.setattr(observability.settings, "langsmith_api_key", "")

    assert enable_langsmith_if_configured() is False


def test_langsmith_is_switched_on_by_a_key(monkeypatch):
    for name in ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT"):
        monkeypatch.setenv(name, "")  # so pytest restores them afterwards
    monkeypatch.setattr(observability.settings, "langsmith_api_key", "ls-test-key")

    assert enable_langsmith_if_configured() is True
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "ls-test-key"


@pytest.mark.parametrize(("log_level", "expected"), [("INFO", logging.WARNING), ("DEBUG", logging.NOTSET)])
def test_chatty_libraries_are_quiet_unless_debugging(monkeypatch, log_level, expected):
    monkeypatch.setattr(observability.settings, "log_level", log_level)
    for library in observability.CHATTY_LIBRARIES:
        monkeypatch.setattr(logging.getLogger(library), "level", logging.NOTSET)

    observability.configure_logging()

    for library in observability.CHATTY_LIBRARIES:
        assert logging.getLogger(library).level == expected
