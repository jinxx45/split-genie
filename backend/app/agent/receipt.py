"""What a receipt looks like once it has been read, and the agent's suggestion for each item.

Plain data and small helpers only. No AI in here.
"""

from decimal import Decimal, InvalidOperation
from typing import Literal, TypedDict

Category = Literal["food", "drink", "alcohol", "dessert"]


class LineItem(TypedDict):
    name: str
    amount_paise: int
    category: Category


class Receipt(TypedDict):
    items: list[LineItem]
    tax_paise: int  # all taxes plus adjustments such as round-off or discounts
    service_charge_paise: int
    printed_total_paise: int  # the total printed at the bottom of the bill


class Suggestion(TypedDict):
    """Who the agent thinks had one item, and why."""

    weights: dict[str, int]  # person -> FULL or HALF; empty means "not sure, ask the user"
    reason: str  # shown to the user on the review screen


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
