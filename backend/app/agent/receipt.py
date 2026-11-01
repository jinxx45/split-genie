"""What a receipt looks like once it has been read, and the agent's suggestion for each item.

Plain data and small helpers only. No AI in here.
"""

from decimal import Decimal, InvalidOperation
from typing import Literal, TypedDict

from app.money.split import FULL, HALF

Category = Literal["food", "drink", "alcohol", "dessert"]


class LineItem(TypedDict):
    name: str
    amount_paise: int
    category: Category
    quantity: int  # how many were ordered, e.g. 3 for "Cold Coffee x3"


class Receipt(TypedDict):
    place: str  # the restaurant or shop name printed on the bill; "" if there isn't one
    items: list[LineItem]
    tax_paise: int  # all taxes plus adjustments such as round-off or discounts
    service_charge_paise: int
    printed_total_paise: int  # the total printed at the bottom of the bill


class Assignment(TypedDict):
    """Who had one item, in one of two ways:
    - shared (by_count False): weights are FULL or HALF shares, e.g. a biryani everyone ate;
    - by count (by_count True): weights are how many each person had, adding up to the item's
      quantity, e.g. "Cold Coffee x3": {"Priya": 1, "Arun": 2}.
    Empty weights mean "not decided yet".
    """

    weights: dict[str, int]
    by_count: bool


class Suggestion(Assignment):
    """The agent's assignment for one item, and why."""

    reason: str  # shown to the user on the review screen


class AssignedItem(Assignment):
    """An item from a finished receipt and who had it, as shown when correcting the split."""

    receipt: int  # index of the receipt in the split
    item: int  # index of the item on that receipt
    name: str
    quantity: int


class Correction(Assignment):
    """A fix to one item: the new, complete assignment."""

    receipt: int
    item: int


def default_suggestion(item: LineItem, people: list[str]) -> Suggestion:
    """What we assume when the note says nothing about an item: food and desserts are shared,
    drinks are usually one person's, so ask (by count when several were ordered)."""
    if item["category"] in ("drink", "alcohol"):
        if item["quantity"] > 1:
            return {"weights": {}, "by_count": True, "reason": "Drinks are usually one each: who had how many?"}
        return {"weights": {}, "by_count": False, "reason": "Drinks are usually one person's: who had it?"}
    return {"weights": {person: FULL for person in people}, "by_count": False, "reason": "Shared by everyone"}


def assignment_problem(assignment: Assignment, quantity: int) -> str | None:
    """Why an item's assignment isn't finished, in words for the user; None if it is."""
    weights = assignment["weights"]
    if not weights:
        return "Every item needs at least one person."
    if assignment["by_count"]:
        if any(count < 1 for count in weights.values()):
            return "Each count must be at least 1."
        assigned = sum(weights.values())
        if assigned < quantity:
            return f"{quantity - assigned} of {quantity} still need a name."
        if assigned > quantity:
            return f"That's {assigned}, but only {quantity} were ordered."
    elif any(weight not in (FULL, HALF) for weight in weights.values()):
        return "Each share must be full or half."
    return None


def receipt_total(receipt: Receipt) -> int:
    """What the receipt adds up to from its lines."""
    items = sum(item["amount_paise"] for item in receipt["items"])
    return items + receipt["tax_paise"] + receipt["service_charge_paise"]


def totals_match(receipt: Receipt) -> bool:
    return receipt_total(receipt) == receipt["printed_total_paise"]


def format_rupees(paise: int) -> str:
    """12325 -> "₹123.25". Integer maths only, no floats."""
    sign = "-" if paise < 0 else ""
    paise = abs(paise)
    return f"{sign}₹{paise // 100}.{paise % 100:02d}"


def to_paise(amount: str) -> int:
    """Turn a printed amount like "₹1,232.50" or "-0.40" into paise (123250, -40).

    Uses Decimal, not float, so "0.1" is exactly 10 paise.
    """
    cleaned = amount.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").strip()
    try:
        rupees = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Not an amount: {amount!r}") from None
    return int(rupees * 100)
