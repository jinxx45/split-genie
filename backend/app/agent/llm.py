"""The AI steps, done with Gemini: reading a receipt photo, suggesting who had what, and
turning the user's correction note into specific changes.

Gemini fills in the Pydantic models below. Everything after that (turning "₹1,232.00" into
paise, adding up, checking names) is plain Python, so it can be tested without the AI.
"""

import base64
import mimetypes
from collections.abc import Callable
from typing import Literal

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.agent.receipt import (
    AssignedItem,
    Assignment,
    AssignmentPlan,
    Category,
    Correction,
    CorrectionPlan,
    LineItem,
    Receipt,
    Suggestion,
    assignment_problem,
    default_suggestion,
    strip_quantity,
    to_paise,
)
from app.config import settings
from app.money.split import FULL, HALF

# --- What Gemini must return. Field descriptions are part of the instructions it sees. ---


class ReadLine(BaseModel):
    name: str = Field(description="Item name as printed, without the quantity, e.g. 'Kingfisher' for 'Kingfisher x2'")
    amount: str = Field(description="The line total exactly as printed, e.g. '400.00'")
    quantity: int = Field(description="How many were ordered, e.g. 2 for 'Kingfisher x2'; 1 if not shown")
    category: Category


class ReadCharge(BaseModel):
    label: str = Field(description="As printed, e.g. 'CGST 2.5%', 'Service Charge', 'Round Off'")
    amount: str = Field(description="Exactly as printed; negative for discounts, e.g. '-0.40'")
    kind: Literal["tax", "service_charge", "adjustment"]


class ReceiptReading(BaseModel):
    place: str = Field(description="The restaurant or shop name printed on the bill; empty if none")
    items: list[ReadLine]
    charges: list[ReadCharge]
    total: str = Field(description="The grand total printed on the bill")


class PersonShare(BaseModel):
    name: str
    share: Literal["full", "half"]
    count: int = Field(
        default=0,
        description="Only if the note says how many of the item this person had, e.g. 1 for "
        "'Priya had one coffee'; otherwise 0",
    )


class ItemSuggestion(BaseModel):
    index: int = Field(description="The item's number from the list")
    people: list[PersonShare] = Field(
        description="Who had it; empty if the note is about this item but doesn't say who had it"
    )
    reason: str = Field(description="A short reason for the user, e.g. 'Ravi doesn't drink'")


class AssignmentSuggestions(BaseModel):
    exceptions: list[ItemSuggestion] = Field(
        description="Only the items the note says something about. Leave every other item out."
    )
    light_eaters: list[str] = Field(
        default_factory=list,
        description="People the note says ate less than the others overall, e.g. 'Prianka didn't eat much'",
    )


class ItemChange(BaseModel):
    receipt: int = Field(description="The receipt number, the first number of the item's id")
    item: int = Field(description="The item number, the second number of the item's id")
    people: list[PersonShare] = Field(description="Everyone who had the item after the fix")


class CorrectionChanges(BaseModel):
    changes: list[ItemChange] = Field(description="Empty if the note doesn't clearly ask for a change")
    light_eaters: list[str] = Field(
        default_factory=list,
        description="People the note says ate less than the others overall, e.g. 'Prianka didn't eat much'",
    )


# --- Turning Gemini's answers into our own types. Pure functions, tested without the AI. ---


def amount_or_zero(amount: str) -> int:
    """An unreadable amount counts as 0. The totals then won't match, which triggers a retry."""
    try:
        return to_paise(amount)
    except ValueError:
        return 0


def reading_to_receipt(reading: ReceiptReading) -> Receipt:
    items: list[LineItem] = []
    for line in reading.items:
        quantity = max(line.quantity, 1)  # never 0 or negative, whatever was read
        items.append(
            {
                "name": strip_quantity(line.name.strip(), quantity),  # in case Gemini kept "x2"
                "amount_paise": amount_or_zero(line.amount),
                "category": line.category,
                "quantity": quantity,
            }
        )
    service_charge = 0
    tax = 0  # taxes plus adjustments (round-off, discounts): both are split in proportion
    for charge in reading.charges:
        if charge.kind == "service_charge":
            service_charge += amount_or_zero(charge.amount)
        else:
            tax += amount_or_zero(charge.amount)

    return {
        "place": reading.place.strip(),
        "items": items,
        "tax_paise": tax,
        "service_charge_paise": service_charge,
        "printed_total_paise": amount_or_zero(reading.total),
    }


def to_assignment(shares: list[PersonShare], people: list[str]) -> Assignment:
    """Gemini's list of people -> an assignment. If any count is given, the item is split by
    count and people without a count are left for the user. Any name not in the split -> no
    one (ask)."""
    by_count = any(share.count > 0 for share in shares)
    people_by_lowercase = {person.lower(): person for person in people}
    weights = {}
    for share in shares:
        person = people_by_lowercase.get(share.name.strip().lower())
        if person is None:
            return {"weights": {}, "by_count": by_count}
        if not by_count:
            weights[person] = FULL if share.share == "full" else HALF
        elif share.count > 0:
            weights[person] = share.count
    return {"weights": weights, "by_count": by_count}


def to_people(names: list[str], people: list[str]) -> list[str]:
    """Names Gemini gave -> the matching people in the split, in the split's order. Any name
    not in the split is dropped."""
    wanted = {name.strip().lower() for name in names}
    return [person for person in people if person.lower() in wanted]


def to_suggestions(
    answer: AssignmentSuggestions, people: list[str], items: list[LineItem]
) -> list[Suggestion]:
    """One suggestion per item, in order. Gemini only lists the items the note is about;
    the rest get the default rule."""
    exceptions_by_index = {exception.index: exception for exception in answer.exceptions}

    suggestions: list[Suggestion] = []
    for index, item in enumerate(items):
        exception = exceptions_by_index.get(index)
        if exception is None:
            suggestions.append(default_suggestion(item, people))
            continue

        assignment = to_assignment(exception.people, people)
        counted = sum(assignment["weights"].values())
        if assignment["by_count"] and counted > item["quantity"]:  # more than were ordered
            suggestions.append({"weights": {}, "by_count": True, "reason": "Not sure who had how many"})
        elif assignment["weights"] or not exception.people:  # valid people, or Gemini said "ask"
            suggestions.append({**assignment, "reason": exception.reason})
        else:  # Gemini named someone who isn't in this split
            suggestions.append({"weights": {}, "by_count": False, "reason": "Not sure who had this"})
    return suggestions


def to_corrections(
    answer: CorrectionChanges, people: list[str], items: list[AssignedItem]
) -> list[Correction]:
    """Keep only changes that point at a real item and leave it fully assigned to real people."""
    items_by_id = {(item["receipt"], item["item"]): item for item in items}

    corrections: list[Correction] = []
    for change in answer.changes:
        item = items_by_id.get((change.receipt, change.item))
        if item is None:
            continue

        assignment = to_assignment(change.people, people)
        if assignment_problem(assignment, item["quantity"]) is None:
            corrections.append({"receipt": change.receipt, "item": change.item, **assignment})
    return corrections


# --- Calling Gemini ---

READ_PROMPT = """You are reading a photo of a restaurant or shop bill from India.

List every ordered line with its name as printed (without the quantity), its line total as
printed, how many were ordered (the quantity, e.g. 2 for "Kingfisher x2" or a Qty column of 2;
1 if the bill doesn't show one), and a category: food, drink (non-alcoholic), alcohol (beer, wine, spirits,
cocktails) or dessert.

List every charge below the items separately, exactly as printed: each tax line (CGST, SGST,
VAT and so on) as "tax", a service charge as "service_charge", and round-off or discounts as
"adjustment" (discounts are negative).

Copy every number exactly as printed. Do not calculate, convert or add anything up.
Finally give the grand total printed on the bill."""

ASSIGN_PROMPT = """People splitting a bill: {people}

Note from the person splitting it: "{note}"

Items:
{items}

List only the items the note says something about, and leave every other item out (they are
handled automatically). For each item you list, say who had it:
- If the note names who had it ("Madhu had the badam milk"), list just them.
- If the note clearly says someone did not have it ("Ravi doesn't drink" for alcohol,
  "Meena left before dessert" for desserts), list everyone else.
- Use "half" for anyone the note says had only a little of it.
- If the note says how many of an item someone had ("Priya had one cold coffee"), give each
  person's count instead. Only give counts the note states; leave anyone else out, so the user
  is asked about the rest.
- If the note is about the item but doesn't say for sure who had it, give an empty list of
  people, so the user is asked. Never guess.
- If the note says someone ate less than the others overall ("Prianka didn't eat much"), put
  them in light_eaters and don't list items just for that. Light eaters pay a half share of
  shared food automatically.
- A preference is not an exclusion: "doesn't take sugar" or "doesn't like spicy food" doesn't
  say whether they had something. Leave such items out unless the note says more.
- Only use names from the list of people.

Use each item's number as its index, and give a short reason written for the user."""


CORRECT_PROMPT = """People splitting a bill: {people}

Items, with who had each one:
{items}

The user rejected the split with this note: "{note}"

Return the changes the note asks for. For each changed item, give its receipt and item numbers
and the full list of people who had it after the change (not just the people who changed).
- If the note says how many of an item someone had, give a count for everyone who had it,
  adding up to the item's quantity.
- If the note says someone ate less than the others overall ("Prianka didn't eat much"), put
  them in light_eaters instead of changing items.
- Only change items the note clearly refers to.
- Only use names from the list of people.
- If the note is unclear, unrelated to who had which item, or not a real sentence, return no
  changes."""


def gemini() -> ChatGoogleGenerativeAI:
    # No temperature: current Gemini models use fixed sampling defaults and ignore it.
    return ChatGoogleGenerativeAI(model=settings.gemini_model, api_key=settings.gemini_api_key)


LoadPhoto = Callable[[str], tuple[bytes, str]]
"""receipt id -> (image bytes, content type such as "image/jpeg")."""


def photo_from_uploads(receipt_id: str) -> tuple[bytes, str]:
    """A photo saved as a file in the uploads folder (used by the terminal scripts)."""
    path = settings.uploads_dir / receipt_id
    return path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/jpeg"


def read_receipt(receipt_id: str, feedback: str | None, load_photo: LoadPhoto = photo_from_uploads) -> Receipt:
    """Read a receipt photo. The app passes load_photo to read it from the database instead."""
    data, mime_type = load_photo(receipt_id)
    image = base64.b64encode(data).decode()

    prompt = READ_PROMPT if feedback is None else f"{READ_PROMPT}\n\n{feedback}"
    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image", "base64": image, "mime_type": mime_type},
        ]
    )
    reading = gemini().with_structured_output(ReceiptReading).invoke([message])
    return reading_to_receipt(reading)


def suggest_assignments(people: list[str], note: str, items: list[LineItem]) -> AssignmentPlan:
    numbered_items = "\n".join(
        f"{index}. {item['name']} ({item['category']}, quantity {item['quantity']})"
        for index, item in enumerate(items)
    )
    prompt = ASSIGN_PROMPT.format(people=", ".join(people), note=note, items=numbered_items)
    answer = gemini().with_structured_output(AssignmentSuggestions).invoke(prompt)
    return {
        "suggestions": to_suggestions(answer, people, items),
        "light_eaters": to_people(answer.light_eaters, people),
    }


def correct_assignments(people: list[str], items: list[AssignedItem], note: str) -> CorrectionPlan:
    listed_items = "\n".join(
        f"{item['receipt']}.{item['item']} {item['name']} (quantity {item['quantity']}): "
        f"{describe_people(item)}"
        for item in items
    )
    prompt = CORRECT_PROMPT.format(people=", ".join(people), items=listed_items, note=note)
    answer = gemini().with_structured_output(CorrectionChanges).invoke(prompt)
    return {
        "corrections": to_corrections(answer, people, items),
        "light_eaters": to_people(answer.light_eaters, people),
    }


def describe_people(assignment: Assignment) -> str:
    """Shared: "Arun, Priya (half)". By count: "Arun had 2, Priya had 1"."""
    weights = assignment["weights"]
    if assignment["by_count"]:
        return ", ".join(f"{name} had {count}" for name, count in weights.items())
    return ", ".join(name if weight == FULL else f"{name} (half)" for name, weight in weights.items())
