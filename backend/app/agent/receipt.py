"""What a receipt looks like once it has been read, and the agent's suggestion for each item.

Plain data and small helpers only. No AI in here.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Literal, TypedDict

from app.money.split import FULL, HALF

Category = Literal["food", "drink", "alcohol", "dessert"]


class LineItem(TypedDict):
    name: str
    amount_paise: int
    category: Category
    quantity: int  # how many were ordered; the name doesn't repeat it ("Cold Coffee", 3)


class Receipt(TypedDict):
    items: list[LineItem]
    tax_paise: int  # all taxes plus adjustments such as round-off or discounts
    service_charge_paise: int
    printed_total_paise: int  # the total printed at the bottom of the bill


class Assignment(TypedDict):
    """Who had one item, in one of two ways:
    - shared (by_count False): weights are FULL or HALF shares, e.g. a biryani everyone ate;
    - by count (by_count True): weights are how many each person had, adding up to the item's
      quantity, e.g. Cold Coffee ×3: {"Priya": 1, "Arun": 2}.
    Empty weights mean "not decided yet".
    """

    weights: dict[str, int]
    by_count: bool


class Suggestion(Assignment):
    """The agent's assignment for one item, and why."""

    reason: str  # shown to the user on the review screen


class AssignmentPlan(TypedDict):
    """What the agent suggests for a receipt: one suggestion per item, and who ate less overall."""

    suggestions: list[Suggestion]
    light_eaters: list[str]


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


class CorrectionPlan(TypedDict):
    """What a correction note asks for: fixes to items, and anyone who ate less overall."""

    corrections: list[Correction]
    light_eaters: list[str]


def default_suggestion(item: LineItem, people: list[str]) -> Suggestion:
    """What we assume when the note says nothing about an item: food and desserts are shared,
    drinks are usually one person's, so ask (by count when several were ordered)."""
    if item["category"] in ("drink", "alcohol"):
        if item["quantity"] > 1:
            return {"weights": {}, "by_count": True, "reason": "Drinks are usually one each: who had how many?"}
        return {"weights": {}, "by_count": False, "reason": "Drinks are usually one person's: who had it?"}
    return {"weights": {person: FULL for person in people}, "by_count": False, "reason": "Shared by everyone"}


def eat_less(item: LineItem, assignment: Assignment, light_eaters: list[str]) -> Assignment:
    """Light eaters pay a half share of shared food and desserts. Drinks, and items split by
    count ("who had how many"), are about what each person actually had, so they stay as they are."""
    if assignment["by_count"] or item["category"] not in ("food", "dessert"):
        return assignment
    weights = {
        person: HALF if person in light_eaters and weight == FULL else weight
        for person, weight in assignment["weights"].items()
    }
    return {"weights": weights, "by_count": False}


def apply_claims(
    items: list[LineItem], assignments: list[Assignment], claims: dict[str, dict[int, int]]
) -> list[Assignment]:
    """The suggested assignments, updated with what friends said they had.

    claims: person -> {item index: weight}. For an item ordered once the weight is FULL ("had
    it") or HALF ("had a little"); for one ordered several times it's how many they had, so a
    claimed item is split by count. Only people who answered change: they're on exactly the
    items they claimed. Everyone who hasn't answered (often the splitter) keeps the suggestion.
    """
    answered = set(claims)
    merged: list[Assignment] = []
    for index, (item, assignment) in enumerate(zip(items, assignments)):
        claimed = {person: answer[index] for person, answer in claims.items() if index in answer}
        by_count = item["quantity"] > 1 if claimed else assignment["by_count"]
        # Keep the suggestion for people who haven't answered, unless the item changed between
        # shared and by count: full/half shares can't be mixed with counts.
        kept = {
            person: weight
            for person, weight in assignment["weights"].items()
            if person not in answered and assignment["by_count"] == by_count
        }
        merged.append({"weights": kept | claimed, "by_count": by_count})
    return merged


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


def strip_quantity(name: str, quantity: int) -> str:
    """"Kingfisher x2" -> "Kingfisher" when 2 were ordered, because the quantity is kept
    separately. Also handles "2 x Kingfisher" and "Kingfisher × 2"."""
    if quantity > 1:
        stripped = re.sub(rf"\s*[x×*]\s*{quantity}$", "", name, flags=re.IGNORECASE)
        stripped = re.sub(rf"^{quantity}\s*[x×*]\s*", "", stripped, flags=re.IGNORECASE)
        return stripped.strip() or name  # never leave an empty name
    return name


def item_label(item: LineItem) -> str:
    """How an item is shown to people: "Cold Coffee ×3", or just "Biryani" for one."""
    return f"{item['name']} ×{item['quantity']}" if item["quantity"] > 1 else item["name"]


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
