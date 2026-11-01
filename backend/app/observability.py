"""Logging for the API and the agent, plus opt-in LangSmith tracing.

Log lines are "event key=value ..." so they read well in a terminal and are easy to search
or parse in a hosting dashboard. They carry ids, counts and timings only: never names,
notes or receipt contents.
"""

import logging
import os
import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langgraph.errors import GraphInterrupt

from app.config import settings

agent_log = logging.getLogger("split_genie.agent")
llm_log = logging.getLogger("split_genie.llm")

# Libraries that log every request at INFO. Our own lines already cover those calls.
CHATTY_LIBRARIES = ("httpx", "google_genai")


def configure_logging() -> None:
    """Send our log lines to the terminal. Call once when the app starts."""
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-5s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    if settings.log_level.upper() != "DEBUG":
        # Hide their routine INFO lines; their warnings and errors still show.
        for library in CHATTY_LIBRARIES:
            logging.getLogger(library).setLevel(logging.WARNING)


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    """log_event(agent_log, INFO, "node finished", node="settle", ms=12)
    -> "node finished node=settle ms=12"."""
    details = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    logger.log(level, f"{event} {details}".strip())


def enable_langsmith_if_configured() -> bool:
    """Turn on LangSmith tracing when a key is set. LangChain reads these environment
    variables itself, so copying them from our settings is all it takes."""
    if not settings.langsmith_api_key:
        return False
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    return True


def elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


class AgentLogHandler(BaseCallbackHandler):
    """Logs each graph step and each LLM call.

    LangChain calls these methods as the graph runs (the "callback" pattern), so the nodes
    themselves need no logging code. Attach it with graph.with_config(callbacks=[...]).
    """

    def __init__(self) -> None:
        # run id -> (what started, which split, when). Filled on start, emptied on end.
        self.nodes: dict[UUID, tuple[str, str | None, float]] = {}
        self.llm_calls: dict[UUID, tuple[str | None, str | None, float]] = {}

    # --- Graph steps ---

    def on_chain_start(self, serialized, inputs, *, run_id, metadata=None, **kwargs) -> None:
        metadata = metadata or {}
        node = metadata.get("langgraph_node")
        # Only the node itself, not the routers and helpers LangGraph runs inside it.
        if node is None or kwargs.get("name") != node:
            return
        split = metadata.get("thread_id")
        self.nodes[run_id] = (node, split, time.perf_counter())
        log_event(agent_log, logging.DEBUG, "node started", split=split, node=node)

    def on_chain_end(self, outputs, *, run_id, **kwargs) -> None:
        if run_id not in self.nodes:
            return
        node, split, started = self.nodes.pop(run_id)
        log_event(agent_log, logging.INFO, "node finished", split=split, node=node, ms=elapsed_ms(started))

    def on_chain_error(self, error, *, run_id, **kwargs) -> None:
        if run_id not in self.nodes:
            return
        node, split, started = self.nodes.pop(run_id)
        if isinstance(error, GraphInterrupt):  # how LangGraph pauses a run: not a failure
            log_event(agent_log, logging.INFO, "node paused for the user", split=split, node=node)
            return
        log_event(
            agent_log,
            logging.ERROR,
            "node failed",
            split=split,
            node=node,
            ms=elapsed_ms(started),
            error=type(error).__name__,
        )

    # --- LLM calls ---

    def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kwargs) -> None:
        metadata = metadata or {}
        model = metadata.get("ls_model_name")
        self.llm_calls[run_id] = (model, metadata.get("langgraph_node"), time.perf_counter())

    def on_llm_end(self, response, *, run_id, **kwargs) -> None:
        if run_id not in self.llm_calls:
            return
        model, node, started = self.llm_calls.pop(run_id)
        usage = getattr(response.generations[0][0], "message", None)
        usage = getattr(usage, "usage_metadata", None) or {}
        log_event(
            llm_log,
            logging.INFO,
            "llm call finished",
            node=node,
            model=model,
            ms=elapsed_ms(started),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )

    def on_llm_error(self, error, *, run_id, **kwargs) -> None:
        if run_id not in self.llm_calls:
            return
        model, node, started = self.llm_calls.pop(run_id)
        log_event(
            llm_log,
            logging.ERROR,
            "llm call failed",
            node=node,
            model=model,
            ms=elapsed_ms(started),
            error=type(error).__name__,
        )
