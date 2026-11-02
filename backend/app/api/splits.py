"""The split endpoints: start a split, see where it is, answer its question, retry a failed step,
mark payments, and list the signed-in user's splits.

Every split is a LangGraph thread, saved in SQLite under its id, so a link can be reopened later.
Signing in is optional; a split started while signed in can only be answered by its owner.
"""

import logging
import secrets
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import ValidationError

from app.agent import llm
from app.agent.graph import build_graph, new_split
from app.agent.receipt import receipt_total
from app.api.accounts import AccountStore, User
from app.api.auth import current_user, get_accounts, require_user
from app.api.payments import PaymentStore
from app.api.schemas import (
    MAX_NOTE_LENGTH,
    MAX_PHOTO_BYTES,
    MAX_PHOTOS,
    PHOTO_TYPES,
    ApprovalIn,
    PayerIn,
    PaymentMarkIn,
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


@lru_cache
def get_payments() -> PaymentStore:
    """Who has paid, kept in the same SQLite file. Tests replace this with a temporary one."""
    return PaymentStore(settings.database_path)


@dataclass
class Context:
    """Everything an endpoint needs, as one dependency instead of four."""

    graph: Any
    payments: PaymentStore
    accounts: AccountStore
    user: User | None  # None: not signed in


def get_context(
    graph=Depends(get_graph),
    payments: PaymentStore = Depends(get_payments),
    accounts: AccountStore = Depends(get_accounts),
    user: User | None = Depends(current_user),
) -> Context:
    return Context(graph, payments, accounts, user)


# --- Endpoints ---


@router.get("")
def my_splits(user: User = Depends(require_user), context: Context = Depends(get_context)) -> dict:
    """The signed-in user's splits, newest first, for the home screen."""
    splits = []
    for split_id, created_at in context.accounts.splits(user.id):
        split = describe(context, split_id)
        result = split["result"]
        splits.append(
            {
                "id": split_id,
                "created_at": created_at,
                "status": split["status"],
                "people": split["people"],
                "title": result["title"] if result else "",
                "total_paise": result["total_paise"] if result else None,
                "payments": len(result["payments"]) if result else 0,
                "paid": sum(1 for payment in result["payments"] if payment["marked_paid_by"]) if result else 0,
            }
        )
    return {"splits": splits}


@router.post("", status_code=201)
def create_split(
    people: list[str] = Form(...),
    note: str = Form("", max_length=MAX_NOTE_LENGTH),
    photos: list[UploadFile] = File(...),
    context: Context = Depends(get_context),
) -> dict:
    """Start a split from receipt photos. Reads the first receipt, then returns its first question."""
    people = clean_people(people)
    if not 1 <= len(photos) <= MAX_PHOTOS:
        raise reject(f"Add 1 to {MAX_PHOTOS} receipt photos.")
    receipt_ids = [save_photo(photo) for photo in photos]

    split_id = secrets.token_urlsafe(9)  # 12 characters, unguessable: the link is the access
    if context.user:  # saved first, so the split is theirs even if reading the bill fails
        context.accounts.add_split(split_id, context.user.id)
        friends = [person for person in people if person.lower() != context.user.name.lower()]
        context.accounts.remember_friends(context.user.id, friends)
    run(context.graph, split_id, new_split(people, note.strip(), receipt_ids))
    return describe(context, split_id)


@router.get("/{split_id}")
def get_split(split_id: str, context: Context = Depends(get_context)) -> dict:
    """Where a split is now. Used when someone opens or reopens a split's link."""
    return describe(context, split_id)


@router.post("/{split_id}/answer")
def answer_split(split_id: str, body: dict[str, Any], context: Context = Depends(get_context)) -> dict:
    """Answer the question the split is waiting on, after checking the answer fits that question."""
    check_can_answer(context, split_id)
    state = load(context.graph, split_id)
    if not state.interrupts:
        raise HTTPException(status_code=409, detail="This split isn't waiting for an answer.")
    question = state.interrupts[0].value

    run(context.graph, split_id, Command(resume=checked_answer(question, body, state.values)))
    return describe(context, split_id)


@router.post("/{split_id}/retry")
def retry_split(split_id: str, context: Context = Depends(get_context)) -> dict:
    """Run the step that failed again (for example after Gemini was briefly unavailable)."""
    check_can_answer(context, split_id)
    state = load(context.graph, split_id)
    if state.interrupts or not state.next:
        raise HTTPException(status_code=409, detail="Nothing to retry.")
    run(context.graph, split_id, None)  # None: carry on from where the split stopped
    return describe(context, split_id)


@router.post("/{split_id}/payments")
def mark_payment(split_id: str, mark: PaymentMarkIn, context: Context = Depends(get_context)) -> dict:
    """Mark one payment of a finished split as paid, or back to waiting. Anyone with the link can:
    friends never need to sign in."""
    state = load(context.graph, split_id)
    if state.interrupts or state.next:
        raise HTTPException(status_code=409, detail="This split isn't finished yet.")
    values = state.values
    if not any(
        payment["sender"] == mark.sender and payment["receiver"] == mark.receiver
        for payment in values["payments"]
    ):
        raise HTTPException(status_code=404, detail=f"{mark.sender} doesn't pay {mark.receiver} in this split.")
    if mark.by not in values["people"]:
        raise reject(f"Not in this split: {mark.by}.")

    if mark.paid:
        context.payments.mark_paid(split_id, mark.sender, mark.receiver, mark.by)
    else:
        context.payments.mark_unpaid(split_id, mark.sender, mark.receiver)
    return describe(context, split_id)


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


def can_answer(context: Context, split_id: str) -> bool:
    """Splits started without signing in can be answered by anyone with the link; others only
    by their owner."""
    owner = context.accounts.owner(split_id)
    return owner is None or (context.user is not None and context.user.id == owner)


def check_can_answer(context: Context, split_id: str) -> None:
    if not can_answer(context, split_id):
        raise HTTPException(status_code=403, detail="Only the person who started this split can answer its questions.")


def describe(context: Context, split_id: str) -> dict:
    """The split as the app sees it: waiting on a question, failed (retry), or done. A done
    split's payments say who marked each one paid (None: still waiting)."""
    state = load(context.graph, split_id)
    values = state.values
    if state.interrupts:
        status, question = "waiting", state.interrupts[0].value
    elif state.next:
        status, question = "failed", None
    else:
        status, question = "done", None

    result = None
    if status == "done":
        marked = context.payments.marked(split_id)
        result = {
            **bill_summary(values["finished"]),
            "shares": values["shares"],
            "breakdown": values["breakdown"],
            "payments": [
                {**payment, "marked_paid_by": marked.get((payment["sender"], payment["receiver"]))}
                for payment in values["payments"]
            ],
        }
    return {
        "id": split_id,
        "status": status,
        "people": values["people"],
        "can_answer": can_answer(context, split_id),
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
            check_review(review, values["people"], values["receipt"]["items"])
            changes = {str(index): assignment.model_dump() for index, assignment in review.changes.items()}
            if review.light_eaters is None:
                return {"changes": changes}
            return {"changes": changes, "light_eaters": review.light_eaters}

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
