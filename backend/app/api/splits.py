"""The split endpoints: start a split, see where it is, answer its question, retry a failed step,
let friends claim what they had, mark payments, and list the signed-in user's splits.

Every split is a LangGraph thread, saved in SQLite under its id, so a link can be reopened later.
Signing in is optional; a split started while signed in can only be answered by its owner.
"""

import logging
import secrets
import sqlite3
from dataclasses import dataclass
from functools import lru_cache, partial
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import ValidationError

from app.agent import llm
from app.agent.graph import build_graph, instant_split, new_split
from app.agent.receipt import apply_claims, receipt_total
from app.api.accounts import AccountStore, User
from app.api.auth import current_user, get_accounts, require_user
from app.api.claims import ClaimStore
from app.api.db import get_database
from app.api.group_store import GroupStore
from app.api.groups import get_groups
from app.api.limits import RateLimit
from app.api.payments import PaymentStore
from app.api.photos import PhotoStore
from app.api.schemas import (
    MAX_NOTE_LENGTH,
    MAX_PHOTO_BYTES,
    MAX_PHOTOS,
    PHOTO_TYPES,
    ApprovalIn,
    ClaimIn,
    InstantSplitIn,
    PayerIn,
    PaymentMarkIn,
    ReceiptIn,
    ReviewIn,
    check_claim,
    check_payers,
    check_review,
    clean_people,
    clean_split_name,
    reject,
)
from app.config import settings
from app.observability import log_event

router = APIRouter(prefix="/api/splits", tags=["splits"])
api_log = logging.getLogger("split_genie.api")


@lru_cache  # built once and shared by every request
def get_graph():
    """The agent wired to Gemini, saving its progress in the app's database. Tests replace this
    with fakes."""
    database = get_database()
    if database.postgres:
        checkpointer = PostgresSaver(database.pool)
        checkpointer.setup()  # creates LangGraph's tables the first time; safe to repeat
    else:
        checkpointer = SqliteSaver(sqlite3.connect(database.sqlite_path, check_same_thread=False))
    read_receipt = partial(llm.read_receipt, load_photo=get_photos().load)
    return build_graph(checkpointer, read_receipt, llm.suggest_assignments, llm.correct_assignments)


@lru_cache
def get_payments() -> PaymentStore:
    """Who has paid. Tests replace this with a temporary one."""
    return PaymentStore(get_database())


@lru_cache
def get_photos() -> PhotoStore:
    """Receipt photos. Tests replace this with a temporary one."""
    return PhotoStore(get_database())


@lru_cache
def get_claims() -> ClaimStore:
    """What friends say they had. Tests replace this with a temporary one."""
    return ClaimStore(get_database())


@dataclass
class Context:
    """Everything an endpoint needs, as one dependency instead of seven."""

    graph: Any
    payments: PaymentStore
    claims: ClaimStore
    photos: PhotoStore
    groups: GroupStore
    accounts: AccountStore
    user: User | None  # None: not signed in


def get_context(
    graph=Depends(get_graph),
    payments: PaymentStore = Depends(get_payments),
    claims: ClaimStore = Depends(get_claims),
    photos: PhotoStore = Depends(get_photos),
    groups: GroupStore = Depends(get_groups),
    accounts: AccountStore = Depends(get_accounts),
    user: User | None = Depends(current_user),
) -> Context:
    return Context(graph, payments, claims, photos, groups, accounts, user)


@lru_cache
def get_split_limit() -> RateLimit:
    return RateLimit(settings.max_splits_per_hour, window_seconds=60 * 60)


def limit_new_splits(request: Request, limit: RateLimit = Depends(get_split_limit)) -> None:
    """Refuse a new split from a visitor who has started too many in the last hour."""
    # Behind Render's proxy, uvicorn sets this from the X-Forwarded-For header (--proxy-headers).
    visitor = request.client.host if request.client else "unknown"
    if not limit.allow(visitor):
        raise HTTPException(
            status_code=429, detail="You've started a lot of splits in the last hour. Please try again later."
        )


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
                "name": split["name"],
                "total_paise": result["total_paise"] if result else None,
                "payments": len(result["payments"]) if result else 0,
                "paid": sum(1 for payment in result["payments"] if payment["marked_paid_by"]) if result else 0,
            }
        )
    return {"splits": splits}


@router.post("", status_code=201)
def create_split(
    name: str = Form(...),
    people: list[str] = Form(...),
    note: str = Form("", max_length=MAX_NOTE_LENGTH),
    photos: list[UploadFile] = File(...),
    group_id: str = Form(""),  # scanning a bill into a group
    added_by: str = Form(""),  # which group member is scanning it
    context: Context = Depends(get_context),
    _: None = Depends(limit_new_splits),
) -> dict:
    """Start a split from receipt photos. Reads the first receipt, then returns its first question."""
    name = clean_split_name(name)
    people = clean_people(people)
    group = None
    if group_id:
        group = check_group_split(context.groups, group_id, people, added_by)
    if not 1 <= len(photos) <= MAX_PHOTOS:
        raise reject(f"Add 1 to {MAX_PHOTOS} receipt photos.")
    receipt_ids = [save_photo(context.photos, photo) for photo in photos]

    split_id = secrets.token_urlsafe(9)  # 12 characters, unguessable: the link is the access
    save_for_user(context, split_id, people)  # first, so the split is theirs even if reading fails
    run(context.graph, split_id, new_split(people, note.strip(), receipt_ids, name, group))
    return describe(context, split_id)


@router.post("/instant", status_code=201)
def create_instant_split(
    body: InstantSplitIn, context: Context = Depends(get_context), _: None = Depends(limit_new_splits)
) -> dict:
    """Split one amount without a photo, e.g. a cab. It's done straight away, and has the same
    link, payments and history as a scanned bill."""
    name = clean_split_name(body.name)
    people = clean_people(body.people)
    outsiders = [person for person in dict.fromkeys([body.paid_by, *body.shares]) if person not in people]
    if outsiders:
        raise reject(f"Not in this split: {', '.join(outsiders)}.")

    split_id = secrets.token_urlsafe(9)
    save_for_user(context, split_id, people)
    state = instant_split(name, people, body.amount_paise, body.paid_by, body.shares)
    # Saved as if the agent's last step had just been approved, so it opens as a finished split.
    context.graph.update_state(config_for(split_id), state, as_node="approve_split")
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
    add_to_group_when_done(context, split_id)
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


@router.post("/{split_id}/claims")
def claim_items(split_id: str, claim: ClaimIn, context: Context = Depends(get_context)) -> dict:
    """A friend says what they had, while the split waits on "who had what". Anyone with the
    link can: friends never need to sign in. The splitter decides whether to use the answers."""
    state = load(context.graph, split_id)
    if not state.interrupts or state.interrupts[0].value["step"] != "review_assignments":
        raise HTTPException(status_code=409, detail="This split isn't asking who had what right now.")
    values = state.values
    check_claim(claim, values["people"], values["receipt"]["items"])
    context.claims.save(split_id, values["current"], claim.person, claim.items)
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
        log_event(
            api_log, logging.ERROR, "split step failed", with_traceback=True, split=split_id, error=type(error).__name__
        )
        raise HTTPException(
            status_code=502, detail="Something went wrong while working on the bill. Please retry."
        ) from None


def save_for_user(context: Context, split_id: str, people: list[str]) -> None:
    """When signed in: the split goes in their history, and the others become their friends."""
    if not context.user:
        return
    context.accounts.add_split(split_id, context.user.id)
    friends = [person for person in people if person.lower() != context.user.name.lower()]
    context.accounts.remember_friends(context.user.id, friends)


def check_group_split(groups: GroupStore, group_id: str, people: list[str], added_by: str) -> dict:
    """A bill scanned into a group: the group must take expenses, and everyone must be in it."""
    group = groups.group(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found.")
    if group.closed_at:
        raise HTTPException(status_code=409, detail="This trip has ended. Reopen it to add expenses.")
    outsiders = [person for person in people if person not in group.members]
    if outsiders:
        raise reject(f"Not in this group: {', '.join(outsiders)}.")
    if added_by not in group.members:
        raise reject("Pick who you are in the group first.")
    return {"id": group_id, "added_by": added_by}


def add_to_group_when_done(context: Context, split_id: str) -> None:
    """Once a group's bill is approved, add it to the group's tab: each person's share, and who
    paid. Adding it again does nothing, so this is safe to repeat."""
    state = load(context.graph, split_id)
    group = state.values.get("group")
    if not group or state.interrupts or state.next:
        return
    values = state.values
    context.groups.add_expense(
        group["id"], values["name"], "bill", bill_summary(values["finished"])["paid"], values["shares"],
        group["added_by"], split_id=split_id,
    )


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
        if question["step"] == "review_assignments":
            # Friends' answers so far, and the suggestions updated with them (used if the
            # splitter taps "Use their answers").
            claims = context.claims.claims(split_id, values["current"])
            claimed = apply_claims(values["receipt"]["items"], values["assignments"], claims)
            question = {**question, "claims": claims, "claimed": claimed}
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
        "name": values.get("name", ""),  # .get: splits saved before names existed still open
        "group": describe_split_group(context, values.get("group")),
        "status": status,
        "people": values["people"],
        "can_answer": can_answer(context, split_id),
        "question": question,
        "result": result,
    }


def describe_split_group(context: Context, group: dict | None) -> dict | None:
    """The group a split belongs to, for a link back to it."""
    if not group:
        return None
    stored = context.groups.group(group["id"])
    return {"id": group["id"], "name": stored.name if stored else "", "added_by": group["added_by"]}


def bill_summary(finished: list[dict]) -> dict:
    """The finished split's total, and who paid, across all its receipts."""
    paid: dict[str, int] = {}
    for done in finished:
        for person, amount in done["paid"].items():
            paid[person] = paid.get(person, 0) + amount
    return {
        "total_paise": sum(receipt_total(done["receipt"]) for done in finished),
        "paid": paid,
    }


def save_photo(store: PhotoStore, photo: UploadFile) -> str:
    """Check an uploaded photo and save it; returns the id the agent reads it by."""
    if photo.content_type not in PHOTO_TYPES:
        raise reject("Photos must be JPEG, PNG, WebP or HEIC images.")
    data = photo.file.read(MAX_PHOTO_BYTES + 1)  # read at most one byte past the limit
    if len(data) > MAX_PHOTO_BYTES:
        raise reject(f"Each photo must be under {MAX_PHOTO_BYTES // (1024 * 1024)} MB.")
    if not data:
        raise reject("A photo was empty.")

    receipt_id = secrets.token_hex(16)  # our own id: never trust the uploaded file's name
    store.save(receipt_id, photo.content_type, data)
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
