"""Stand-ins for the AI steps, so graph tests run without Gemini or an API key."""

from app.agent.receipt import AssignedItem, Correction, LineItem, Receipt, Suggestion
from app.money.split import FULL

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
        {"name": "Filter Coffee x3", "amount_paise": 9000, "category": "drink"},
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


def read_receipt(receipt_id: str, feedback: str | None) -> Receipt:
    """- "dinner" and "lunch" read correctly.
    - "blurry" misreads, then reads correctly once given feedback on a retry.
    - "unreadable" never adds up.
    """
    if receipt_id == "lunch":
        return LUNCH
    if receipt_id == "blurry" and feedback is not None:
        return DINNER
    if receipt_id in ("blurry", "unreadable"):
        return DINNER_MISREAD
    return DINNER


def suggest_assignments(people: list[str], note: str, items: list[LineItem]) -> list[Suggestion]:
    """Food and desserts go to everyone; drinks with alcohol are left for the user."""
    suggestions: list[Suggestion] = []
    for item in items:
        if item["category"] == "alcohol":
            suggestions.append({"weights": {}, "reason": "Not sure who drank"})
        else:
            suggestions.append({"weights": {p: FULL for p in people}, "reason": "Shared"})
    return suggestions


def correct_assignments(people: list[str], items: list[AssignedItem], note: str) -> list[Correction]:
    """Understands one kind of note: "<name> didn't have dessert". Anything else: no changes."""
    if "dessert" not in note.lower():
        return []
    named = [person for person in people if person.lower() in note.lower()]
    corrections: list[Correction] = []
    for item in items:
        if "Jamun" in item["name"]:
            weights = {p: w for p, w in item["weights"].items() if p not in named}
            corrections.append({"receipt": item["receipt"], "item": item["item"], "weights": weights})
    return corrections
