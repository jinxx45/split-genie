"""Reading a receipt. For now this returns fake receipts; Milestone 4 swaps in a vision LLM."""

from typing import TypedDict


class LineItem(TypedDict):
    name: str
    amount_paise: int
    category: str  # "food", "alcohol" or "dessert"


class Receipt(TypedDict):
    items: list[LineItem]
    tax_paise: int
    service_charge_paise: int
    printed_total_paise: int  # the total printed at the bottom of the bill


def receipt_total(receipt: Receipt) -> int:
    """What the receipt adds up to from its lines."""
    items = sum(item["amount_paise"] for item in receipt["items"])
    return items + receipt["tax_paise"] + receipt["service_charge_paise"]


def totals_match(receipt: Receipt) -> bool:
    return receipt_total(receipt) == receipt["printed_total_paise"]


DINNER: Receipt = {
    "items": [
        {"name": "Chicken Biryani", "amount_paise": 60000, "category": "food"},
        {"name": "Kingfisher x2", "amount_paise": 40000, "category": "alcohol"},
        {"name": "Gulab Jamun", "amount_paise": 12000, "category": "dessert"},
    ],
    "tax_paise": 5600,
    "service_charge_paise": 5600,
    "printed_total_paise": 123200,
}

LUNCH: Receipt = {
    "items": [
        {"name": "Meals", "amount_paise": 36000, "category": "food"},
        {"name": "Filter Coffee x3", "amount_paise": 9000, "category": "food"},
    ],
    "tax_paise": 2250,
    "service_charge_paise": 0,
    "printed_total_paise": 47250,
}

# The biryani misread as ₹60.00 instead of ₹600.00, so the lines don't add up.
DINNER_MISREAD: Receipt = {
    **DINNER,
    "items": [{**DINNER["items"][0], "amount_paise": 6000}, *DINNER["items"][1:]],
}


def extract_receipt(receipt_id: str, attempt: int) -> Receipt:
    """Fake extraction.

    - "dinner" and "lunch" read correctly.
    - "blurry" misreads on the first attempt and reads correctly on a retry.
    - "unreadable" never adds up, however many times it is retried.
    """
    if receipt_id == "lunch":
        return LUNCH
    if receipt_id == "blurry" and attempt > 1:
        return DINNER
    if receipt_id in ("blurry", "unreadable"):
        return DINNER_MISREAD
    return DINNER
