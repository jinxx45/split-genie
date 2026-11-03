"""Stand-ins for the AI steps, so graph tests run without Gemini or an API key."""

from app.agent.receipt import (
    AssignedItem,
    AssignmentPlan,
    Correction,
    CorrectionPlan,
    LineItem,
    Receipt,
    Suggestion,
)
from app.money.split import FULL

DINNER: Receipt = {
    "items": [
        {"name": "Chicken Biryani", "amount_paise": 60000, "category": "food", "quantity": 1},
        {"name": "Kingfisher", "amount_paise": 40000, "category": "alcohol", "quantity": 2},
        {"name": "Gulab Jamun", "amount_paise": 12000, "category": "dessert", "quantity": 1},
    ],
    "tax_paise": 5600,
    "service_charge_paise": 5600,
    "printed_total_paise": 123200,
}

LUNCH: Receipt = {
    "items": [
        {"name": "Meals", "amount_paise": 36000, "category": "food", "quantity": 1},
        {"name": "Filter Coffee", "amount_paise": 9000, "category": "drink", "quantity": 3},
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


def light_eaters_in(note: str, people: list[str]) -> list[str]:
    """Understands "<name> didn't eat much"."""
    if "eat much" not in note.lower():
        return []
    return [person for person in people if person.lower() in note.lower()]


def suggest_assignments(people: list[str], note: str, items: list[LineItem]) -> AssignmentPlan:
    """Food and desserts go to everyone; drinks with alcohol are left for the user."""
    suggestions: list[Suggestion] = []
    for item in items:
        if item["category"] == "alcohol":
            suggestions.append({"weights": {}, "by_count": False, "reason": "Not sure who drank"})
        else:
            suggestions.append({"weights": {p: FULL for p in people}, "by_count": False, "reason": "Shared"})
    return {"suggestions": suggestions, "light_eaters": light_eaters_in(note, people)}


def correct_assignments(people: list[str], items: list[AssignedItem], note: str) -> CorrectionPlan:
    """Understands "<name> didn't have dessert" and "<name> didn't eat much". Anything else: nothing."""
    light_eaters = light_eaters_in(note, people)
    if "dessert" not in note.lower():
        return {"corrections": [], "light_eaters": light_eaters}
    named = [person for person in people if person.lower() in note.lower()]
    corrections: list[Correction] = []
    for item in items:
        if "Jamun" in item["name"]:
            weights = {p: w for p, w in item["weights"].items() if p not in named}
            corrections.append(
                {"receipt": item["receipt"], "item": item["item"], "weights": weights, "by_count": False}
            )
    return {"corrections": corrections, "light_eaters": light_eaters}
