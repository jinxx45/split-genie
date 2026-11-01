"""The Split Genie agent: a LangGraph state graph that pauses for the user.

Flow (see the PRD diagram):
    extract_items -> (totals match? retry up to 2 times) -> confirm_items [pause]
    -> auto_assign -> review_assignments [pause; asked again until every item has someone]
    -> ask_payer [pause] -> finish_receipt -> (more receipts? back to extract_items)
    -> compute_shares -> settle
"""

from dataclasses import asdict
from typing import TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agent.extract import Receipt, extract_receipt, receipt_total, totals_match
from app.money.settle import settle
from app.money.split import FULL, Bill, Item, balances, compute_shares

MAX_ATTEMPTS = 3  # the first read plus 2 retries


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
    paid: dict[str, int]  # who paid the current receipt, in paise
    finished: list[FinishedReceipt]
    shares: dict[str, int]
    balances: dict[str, int]
    payments: list[dict]


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
        "paid": {},
        "finished": [],
        "shares": {},
        "balances": {},
        "payments": [],
    }


# --- Nodes: each takes the state and returns only the fields it changes ---


def extract_items(state: SplitState) -> dict:
    receipt_id = state["receipt_ids"][state["current"]]
    attempt = state["attempts"] + 1
    return {"receipt": extract_receipt(receipt_id, attempt), "attempts": attempt}


def confirm_items(state: SplitState) -> dict:
    """Pause so the user can check and fix the items. They send back the corrected receipt."""
    receipt = state["receipt"]
    corrected = interrupt(
        {"step": "confirm_items", "receipt": receipt, "totals_match": totals_match(receipt)}
    )
    return {"receipt": corrected}


def auto_assign(state: SplitState) -> dict:
    """Fake rule until Milestone 4: food and desserts are shared by everyone, drinks are asked about."""
    assignments = []
    for item in state["receipt"]["items"]:
        if item["category"] == "alcohol":
            assignments.append({})
        else:
            assignments.append({person: FULL for person in state["people"]})
    return {"assignments": assignments}


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


def build_graph(checkpointer: BaseCheckpointSaver):
    builder = StateGraph(SplitState)

    builder.add_node("extract_items", extract_items)
    builder.add_node("confirm_items", confirm_items)
    builder.add_node("auto_assign", auto_assign)
    builder.add_node("review_assignments", review_assignments)
    builder.add_node("ask_payer", ask_payer)
    builder.add_node("finish_receipt", finish_receipt)
    builder.add_node("compute_shares", compute_shares_node)
    builder.add_node("settle", settle_node)

    builder.add_edge(START, "extract_items")
    builder.add_conditional_edges("extract_items", after_extract)
    builder.add_edge("confirm_items", "auto_assign")
    builder.add_edge("auto_assign", "review_assignments")
    builder.add_conditional_edges("review_assignments", after_review)  # still unclear? ask again
    builder.add_conditional_edges("ask_payer", after_payer)
    builder.add_conditional_edges("finish_receipt", after_finish)
    builder.add_edge("compute_shares", "settle")
    builder.add_edge("settle", END)

    return builder.compile(checkpointer=checkpointer)
