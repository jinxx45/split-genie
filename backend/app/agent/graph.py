"""The Split Genie agent: a LangGraph state graph that pauses for the user.

Flow (see the PRD diagram):
    extract_items -> (totals match? retry up to 2 times) -> confirm_items [pause]
    -> auto_assign -> review_assignments [pause; asked again until every item has someone]
    -> ask_payer [pause] -> finish_receipt -> (more receipts? back to extract_items)
    -> compute_shares -> settle -> approve_split [pause]
    -> approved: end | rejected with a note: apply_correction -> back to compute_shares
"""

from collections.abc import Callable
from dataclasses import asdict
from functools import partial
from typing import TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agent.receipt import (
    AssignedItem,
    Correction,
    LineItem,
    Receipt,
    Suggestion,
    format_rupees,
    receipt_total,
    totals_match,
)
from app.money.settle import settle
from app.money.split import FULL, Bill, Item, balances, compute_shares

MAX_ATTEMPTS = 3  # the first read plus 2 retries
MIN_NOTE_WORDS = 2  # "wrong" alone can't be acted on; "Priya brownie" can
MAX_NOTE_LENGTH = 500

# The AI steps, passed in so tests can use fakes and the app can use Gemini.
ReadReceipt = Callable[[str, str | None], Receipt]
"""(receipt id, feedback about the previous misread or None) -> the receipt as read."""

SuggestAssignments = Callable[[list[str], str, list[LineItem]], list[Suggestion]]
"""(people, the splitter's note, items) -> one suggestion per item, in the same order."""

CorrectAssignments = Callable[[list[str], list[AssignedItem], str], list[Correction]]
"""(people, every finished item and who had it, the user's note) -> valid fixes; [] if none."""


class FinishedReceipt(TypedDict):
    receipt: Receipt
    assignments: list[dict[str, int]]
    paid: dict[str, int]


class SplitState(TypedDict):
    people: list[str]
    note: str
    receipt_ids: list[str]
    current: int  # index into receipt_ids of the receipt being worked on
    attempts: int  # extraction attempts for the current receipt
    receipt: Receipt | None
    assignments: list[dict[str, int]]  # one per item: person -> FULL/HALF; empty = not decided
    reasons: list[str]  # one per item: why it was assigned that way
    paid: dict[str, int]  # who paid the current receipt, in paise
    finished: list[FinishedReceipt]
    shares: dict[str, int]
    balances: dict[str, int]
    payments: list[dict]
    approved: bool
    correction_note: str  # why the user rejected the split
    approval_error: str | None  # shown on the approval screen when an answer couldn't be used


def new_split(people: list[str], note: str, receipt_ids: list[str]) -> SplitState:
    """The starting state for a split."""
    return {
        "people": people,
        "note": note,
        "receipt_ids": receipt_ids,
        "current": 0,
        "attempts": 0,
        "receipt": None,
        "assignments": [],
        "reasons": [],
        "paid": {},
        "finished": [],
        "shares": {},
        "balances": {},
        "payments": [],
        "approved": False,
        "correction_note": "",
        "approval_error": None,
    }


# --- Nodes: each takes the state and returns only the fields it changes ---


def extract_items(state: SplitState, read_receipt: ReadReceipt) -> dict:
    receipt_id = state["receipt_ids"][state["current"]]

    feedback = None
    previous = state["receipt"]
    if previous is not None:  # a retry: tell the reader what went wrong last time
        feedback = (
            f"Your last reading added up to {format_rupees(receipt_total(previous))}, "
            f"but the printed total is {format_rupees(previous['printed_total_paise'])}. "
            "Read every line again carefully."
        )

    return {"receipt": read_receipt(receipt_id, feedback), "attempts": state["attempts"] + 1}


def confirm_items(state: SplitState) -> dict:
    """Pause so the user can check and fix the items. They send back the corrected receipt."""
    receipt = state["receipt"]
    corrected = interrupt(
        {"step": "confirm_items", "receipt": receipt, "totals_match": totals_match(receipt)}
    )
    return {"receipt": corrected}


def auto_assign(state: SplitState, suggest_assignments: SuggestAssignments) -> dict:
    """Suggest who had each item. With no note there is nothing to go on, so everyone shares
    everything (no AI call needed); the user fixes exceptions on the review screen."""
    items = state["receipt"]["items"]
    if state["note"].strip():
        suggestions = suggest_assignments(state["people"], state["note"], items)
    else:
        everyone = {person: FULL for person in state["people"]}
        suggestions = [{"weights": everyone, "reason": "Shared by everyone"} for _ in items]

    return {
        "assignments": [suggestion["weights"] for suggestion in suggestions],
        "reasons": [suggestion["reason"] for suggestion in suggestions],
    }


def review_assignments(state: SplitState) -> dict:
    """Pause and show every item with the suggested people, so the user can fix any of them.

    Unclear items (no suggestion) must be answered. The answer lists only what the user
    changed: {"changes": {item index: {person: weight}}}. No changes means "the suggestions
    are right". (The answer is wrapped in "changes" because LangGraph treats a bare empty
    dict sent with `resume` as "no answer".)
    """
    unclear = unclear_items(state)
    items = []
    for index, item in enumerate(state["receipt"]["items"]):
        items.append(
            {
                "index": index,
                "item": item,
                "suggested": state["assignments"][index],
                "reason": state["reasons"][index],
                "needs_answer": index in unclear,
            }
        )
    answer = interrupt({"step": "review_assignments", "people": state["people"], "items": items})

    assignments = list(state["assignments"])
    for index, weights in answer["changes"].items():
        assignments[int(index)] = weights
    return {"assignments": assignments}


def ask_payer(state: SplitState) -> dict:
    """Pause and ask who paid this receipt. Answer: {person: paise}, adding up to the total."""
    paid = interrupt(
        {
            "step": "payer",
            "people": state["people"],
            "total_paise": receipt_total(state["receipt"]),
        }
    )
    return {"paid": paid}


def finish_receipt(state: SplitState) -> dict:
    """File the current receipt away and move on to the next one."""
    done: FinishedReceipt = {
        "receipt": state["receipt"],
        "assignments": state["assignments"],
        "paid": state["paid"],
    }
    return {
        "finished": state["finished"] + [done],
        "current": state["current"] + 1,
        "attempts": 0,
        "receipt": None,
        "assignments": [],
        "reasons": [],
        "paid": {},
    }


def compute_shares_node(state: SplitState) -> dict:
    """Plain Python from here on: the LLM never does money maths."""
    owed: dict[str, int] = {}
    paid: dict[str, int] = {}
    for done in state["finished"]:
        receipt = done["receipt"]
        bill = Bill(
            items=[
                Item(item["name"], item["amount_paise"], weights)
                for item, weights in zip(receipt["items"], done["assignments"])
            ],
            tax_paise=receipt["tax_paise"],
            service_charge_paise=receipt["service_charge_paise"],
        )
        for person, amount in compute_shares(bill).items():
            owed[person] = owed.get(person, 0) + amount
        for person, amount in done["paid"].items():
            paid[person] = paid.get(person, 0) + amount

    return {"shares": owed, "balances": balances(owed, paid)}


def settle_node(state: SplitState) -> dict:
    return {"payments": [asdict(payment) for payment in settle(state["balances"])]}


def approve_split(state: SplitState) -> dict:
    """Pause for final sign-off. Answer: {"approved": True} or {"approved": False, "note": "..."}."""
    answer = interrupt(
        {
            "step": "approve",
            "shares": state["shares"],
            "payments": state["payments"],
            "error": state["approval_error"],
        }
    )
    error = check_approval(answer)
    if error:
        return {"approval_error": error}
    return {
        "approved": answer["approved"],
        "correction_note": (answer.get("note") or "").strip(),
        "approval_error": None,
    }


def apply_correction(state: SplitState, correct_assignments: CorrectAssignments) -> dict:
    """Turn the user's note into changes to who had what. If nothing usable comes out
    (gibberish, or a note about something other than items), ask again with a hint."""
    corrections = correct_assignments(
        state["people"], assigned_items(state["finished"]), state["correction_note"]
    )
    if not corrections:
        return {
            "approval_error": (
                "Couldn't match that to any item. Name the person and the item, for example "
                "\"Priya didn't have the brownie\". Only who had which item can be changed here."
            )
        }

    # Copy before changing: nodes return new values instead of editing the state in place.
    finished = [dict(done, assignments=list(done["assignments"])) for done in state["finished"]]
    for correction in corrections:
        finished[correction["receipt"]]["assignments"][correction["item"]] = correction["weights"]
    return {"finished": finished, "approval_error": None}


# --- Plain helpers ---


def check_approval(answer: object) -> str | None:
    """Why an approval answer can't be used, or None if it's fine."""
    if not isinstance(answer, dict) or not isinstance(answer.get("approved"), bool):
        return "Please approve the split, or say what's wrong."

    note = answer.get("note") or ""
    if not isinstance(note, str):
        return "The note must be text."
    note = note.strip()

    if answer["approved"]:
        return "A note is only needed when something is wrong." if note else None

    words_with_letters = [word for word in note.split() if any(char.isalpha() for char in word)]
    if len(words_with_letters) < MIN_NOTE_WORDS:
        return "Please say what's wrong, for example \"Priya didn't have the brownie\"."
    if len(note) > MAX_NOTE_LENGTH:
        return f"Please keep the note under {MAX_NOTE_LENGTH} characters."
    return None


def assigned_items(finished: list[FinishedReceipt]) -> list[AssignedItem]:
    """Every item across the finished receipts, with who had it."""
    items: list[AssignedItem] = []
    for receipt_index, done in enumerate(finished):
        for item_index, item in enumerate(done["receipt"]["items"]):
            items.append(
                {
                    "receipt": receipt_index,
                    "item": item_index,
                    "name": item["name"],
                    "weights": done["assignments"][item_index],
                }
            )
    return items


# --- Routing: functions that pick the next node ---


def unclear_items(state: SplitState) -> list[int]:
    return [index for index, weights in enumerate(state["assignments"]) if not weights]


def after_extract(state: SplitState) -> str:
    if totals_match(state["receipt"]) or state["attempts"] >= MAX_ATTEMPTS:
        return "confirm_items"
    return "extract_items"


def after_review(state: SplitState) -> str:
    return "review_assignments" if unclear_items(state) else "ask_payer"


def after_payer(state: SplitState) -> str:
    if sum(state["paid"].values()) != receipt_total(state["receipt"]):
        return "ask_payer"  # payments don't add up to the bill: ask again
    return "finish_receipt"


def after_finish(state: SplitState) -> str:
    if state["current"] < len(state["receipt_ids"]):
        return "extract_items"
    return "compute_shares"


def after_approval(state: SplitState) -> str:
    if state["approval_error"]:
        return "approve_split"  # the answer couldn't be used: ask again, showing why
    return END if state["approved"] else "apply_correction"


def after_correction(state: SplitState) -> str:
    return "approve_split" if state["approval_error"] else "compute_shares"


def build_graph(
    checkpointer: BaseCheckpointSaver,
    read_receipt: ReadReceipt,
    suggest_assignments: SuggestAssignments,
    correct_assignments: CorrectAssignments,
):
    builder = StateGraph(SplitState)

    builder.add_node("extract_items", partial(extract_items, read_receipt=read_receipt))
    builder.add_node("confirm_items", confirm_items)
    builder.add_node(
        "auto_assign", partial(auto_assign, suggest_assignments=suggest_assignments)
    )
    builder.add_node("review_assignments", review_assignments)
    builder.add_node("ask_payer", ask_payer)
    builder.add_node("finish_receipt", finish_receipt)
    builder.add_node("compute_shares", compute_shares_node)
    builder.add_node("settle", settle_node)
    builder.add_node("approve_split", approve_split)
    builder.add_node(
        "apply_correction", partial(apply_correction, correct_assignments=correct_assignments)
    )

    builder.add_edge(START, "extract_items")
    builder.add_conditional_edges("extract_items", after_extract)
    builder.add_edge("confirm_items", "auto_assign")
    builder.add_edge("auto_assign", "review_assignments")
    builder.add_conditional_edges("review_assignments", after_review)  # still unclear? ask again
    builder.add_conditional_edges("ask_payer", after_payer)
    builder.add_conditional_edges("finish_receipt", after_finish)
    builder.add_edge("compute_shares", "settle")
    builder.add_edge("settle", "approve_split")
    builder.add_conditional_edges("approve_split", after_approval)
    builder.add_conditional_edges("apply_correction", after_correction)

    return builder.compile(checkpointer=checkpointer)
