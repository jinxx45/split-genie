"""The split endpoints: start a split, see where it is, answer its question, retry a failed step.

Every split is a LangGraph thread, saved in SQLite under its id, so a link can be reopened later.
"""

import logging
import secrets
import sqlite3
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import ValidationError

from app.agent import llm
from app.agent.graph import build_graph, new_split
from app.agent.receipt import receipt_total
from app.api.schemas import (
    MAX_NOTE_LENGTH,
    MAX_PHOTO_BYTES,
    MAX_PHOTOS,
    PHOTO_TYPES,
    ApprovalIn,
    PayerIn,
    ReceiptIn,
    ReviewIn,
    check_payers,
    check_review,
    clean_people,
    reject,
)
from app.config import settings
from app.observability import log_event

router = APIRouter(prefix="/api/splits", tags=["splits"])
api_log = logging.getLogger("split_genie.api")


@lru_cache  # built once and shared by every request
def get_graph():
    """The agent wired to Gemini and to the SQLite file. Tests replace this with fakes."""
    connection = sqlite3.connect(settings.database_path, check_same_thread=False)
    return build_graph(
        SqliteSaver(connection), llm.read_receipt, llm.suggest_assignments, llm.correct_assignments
    )


# --- Endpoints ---


@router.post("", status_code=201)
def create_split(
    people: list[str] = Form(...),
    note: str = Form("", max_length=MAX_NOTE_LENGTH),
    photos: list[UploadFile] = File(...),
    graph=Depends(get_graph),
) -> dict:
    """Start a split from receipt photos. Reads the first receipt, then returns its first question."""
    people = clean_people(people)
    if not 1 <= len(photos) <= MAX_PHOTOS:
        raise reject(f"Add 1 to {MAX_PHOTOS} receipt photos.")
    receipt_ids = [save_photo(photo) for photo in photos]

    split_id = secrets.token_urlsafe(9)  # 12 characters, unguessable: the link is the access
    run(graph, split_id, new_split(people, note.strip(), receipt_ids))
    return describe(graph, split_id)


@router.get("/{split_id}")
def get_split(split_id: str, graph=Depends(get_graph)) -> dict:
    """Where a split is now. Used when someone opens or reopens a split's link."""
    return describe(graph, split_id)


@router.post("/{split_id}/answer")
def answer_split(split_id: str, body: dict[str, Any], graph=Depends(get_graph)) -> dict:
    """Answer the question the split is waiting on, after checking the answer fits that question."""
    state = load(graph, split_id)
    if not state.interrupts:
        raise HTTPException(status_code=409, detail="This split isn't waiting for an answer.")
    question = state.interrupts[0].value

    run(graph, split_id, Command(resume=checked_answer(question, body, state.values)))
    return describe(graph, split_id)


@router.post("/{split_id}/retry")
def retry_split(split_id: str, graph=Depends(get_graph)) -> dict:
    """Run the step that failed again (for example after Gemini was briefly unavailable)."""
    state = load(graph, split_id)
    if state.interrupts or not state.next:
        raise HTTPException(status_code=409, detail="Nothing to retry.")
    run(graph, split_id, None)  # None: carry on from where the split stopped
    return describe(graph, split_id)


# --- Helpers ---


def config_for(split_id: str) -> dict:
    return {"configurable": {"thread_id": split_id}}


def load(graph, split_id: str):
    state = graph.get_state(config_for(split_id))
    if not state.values:  # no saved state: this id was never created
        raise HTTPException(status_code=404, detail="Split not found.")
    return state


def run(graph, split_id: str, graph_input) -> None:
    """Run the agent until its next pause. A failure (usually Gemini) becomes a 502 the app can
    show with a retry button; the step that failed is remembered, so /retry continues from it."""
    try:
        graph.invoke(graph_input, config_for(split_id))
    except Exception as error:
        log_event(api_log, logging.ERROR, "split step failed", split=split_id, error=type(error).__name__)
        raise HTTPException(
            status_code=502, detail="Something went wrong while working on the bill. Please retry."
        ) from None


def describe(graph, split_id: str) -> dict:
    """The split as the app sees it: waiting on a question, failed (retry), or done."""
    state = load(graph, split_id)
    values = state.values
    if state.interrupts:
        status, question = "waiting", state.interrupts[0].value
    elif state.next:
        status, question = "failed", None
    else:
        status, question = "done", None

    result = None
    if status == "done":
        result = {
            **bill_summary(values["finished"]),
            "shares": values["shares"],
            "breakdown": values["breakdown"],
            "payments": values["payments"],
        }
    return {
        "id": split_id,
        "status": status,
        "people": values["people"],
        "question": question,
        "result": result,
    }


def bill_summary(finished: list[dict]) -> dict:
    """What the finished split was for, its total, and who paid, across all its receipts."""
    # .get: splits saved before receipts had a place still open.
    places = [done["receipt"].get("place", "") for done in finished]
    paid: dict[str, int] = {}
    for done in finished:
        for person, amount in done["paid"].items():
            paid[person] = paid.get(person, 0) + amount
    return {
        "title": " + ".join(dict.fromkeys(place for place in places if place)),  # unique, in order
        "total_paise": sum(receipt_total(done["receipt"]) for done in finished),
        "paid": paid,
    }


def save_photo(photo: UploadFile) -> str:
    extension = PHOTO_TYPES.get(photo.content_type or "")
    if extension is None:
        raise reject("Photos must be JPEG, PNG, WebP or HEIC images.")
    data = photo.file.read(MAX_PHOTO_BYTES + 1)  # read at most one byte past the limit
    if len(data) > MAX_PHOTO_BYTES:
        raise reject(f"Each photo must be under {MAX_PHOTO_BYTES // (1024 * 1024)} MB.")
    if not data:
        raise reject("A photo was empty.")

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    receipt_id = f"{secrets.token_hex(16)}{extension}"  # our own name: never trust the uploaded one
    (settings.uploads_dir / receipt_id).write_bytes(data)
    return receipt_id


def checked_answer(question: dict, body: dict, values: dict) -> Any:
    """Validate an answer for the step it answers, and return it in the shape the agent expects."""
    step = question["step"]
    try:
        if step == "confirm_items":
            return ReceiptIn.model_validate(body).model_dump()

        if step == "review_assignments":
            review = ReviewIn.model_validate(body)
            check_review(review, values["people"], len(values["receipt"]["items"]))
            return {"changes": {str(index): weights for index, weights in review.changes.items()}}

        if step == "payer":
            payer = PayerIn.model_validate(body)
            check_payers(payer, values["people"], receipt_total(values["receipt"]))
            return payer.paid

        if step == "approve":
            return ApprovalIn.model_validate(body).model_dump(exclude_none=True)
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        raise reject(f"{where}: {first['msg']}" if where else first["msg"]) from None

    raise HTTPException(status_code=500, detail=f"Unknown step: {step}")
