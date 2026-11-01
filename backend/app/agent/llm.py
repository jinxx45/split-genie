"""The AI steps, done with Gemini: reading a receipt photo, suggesting who had what, and
turning the user's correction note into specific changes.

Gemini fills in the Pydantic models below. Everything after that (turning "₹1,232.00" into
paise, adding up, checking names) is plain Python, so it can be tested without the AI.
"""

import base64
import mimetypes
from typing import Literal

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.agent.receipt import (
    AssignedItem,
    Category,
    Correction,
    LineItem,
    Receipt,
    Suggestion,
    to_paise,
)
from app.config import settings
from app.money.split import FULL, HALF

# --- What Gemini must return. Field descriptions are part of the instructions it sees. ---


class ReadLine(BaseModel):
    name: str = Field(description="Item name as printed, keeping quantities, e.g. 'Kingfisher x2'")
    amount: str = Field(description="The line total exactly as printed, e.g. '400.00'")
    category: Category


class ReadCharge(BaseModel):
    label: str = Field(description="As printed, e.g. 'CGST 2.5%', 'Service Charge', 'Round Off'")
    amount: str = Field(description="Exactly as printed; negative for discounts, e.g. '-0.40'")
    kind: Literal["tax", "service_charge", "adjustment"]


class ReceiptReading(BaseModel):
    items: list[ReadLine]
    charges: list[ReadCharge]
    total: str = Field(description="The grand total printed on the bill")


class PersonShare(BaseModel):
    name: str
    share: Literal["full", "half"]


class ItemSuggestion(BaseModel):
    index: int = Field(description="The item's number from the list")
    people: list[PersonShare] = Field(description="Empty if the note leaves it unclear")
    reason: str = Field(description="A short reason for the user, e.g. 'Ravi doesn't drink'")


class AssignmentSuggestions(BaseModel):
    items: list[ItemSuggestion]


class ItemChange(BaseModel):
    receipt: int = Field(description="The receipt number, the first number of the item's id")
    item: int = Field(description="The item number, the second number of the item's id")
    people: list[PersonShare] = Field(description="Everyone who had the item after the fix")


class CorrectionChanges(BaseModel):
    changes: list[ItemChange] = Field(description="Empty if the note doesn't clearly ask for a change")


# --- Turning Gemini's answers into our own types. Pure functions, tested without the AI. ---


def amount_or_zero(amount: str) -> int:
    """An unreadable amount counts as 0. The totals then won't match, which triggers a retry."""
    try:
        return to_paise(amount)
    except ValueError:
        return 0


def reading_to_receipt(reading: ReceiptReading) -> Receipt:
    items: list[LineItem] = [
        {"name": line.name, "amount_paise": amount_or_zero(line.amount), "category": line.category}
        for line in reading.items
    ]
    service_charge = 0
    tax = 0  # taxes plus adjustments (round-off, discounts): both are split in proportion
    for charge in reading.charges:
        if charge.kind == "service_charge":
            service_charge += amount_or_zero(charge.amount)
        else:
            tax += amount_or_zero(charge.amount)

    return {
        "items": items,
        "tax_paise": tax,
        "service_charge_paise": service_charge,
        "printed_total_paise": amount_or_zero(reading.total),
    }


def to_suggestions(
    answer: AssignmentSuggestions, people: list[str], item_count: int
) -> list[Suggestion]:
    """One suggestion per item, in order. Anything Gemini got wrong becomes "ask the user"."""
    people_by_lowercase = {person.lower(): person for person in people}
    answers_by_index = {item.index: item for item in answer.items}

    suggestions: list[Suggestion] = []
    for index in range(item_count):
        item = answers_by_index.get(index)
        if item is None:
            suggestions.append({"weights": {}, "reason": "Couldn't tell who had this"})
            continue

        weights = {}
        for share in item.people:
            person = people_by_lowercase.get(share.name.strip().lower())
            if person is None:  # a name that isn't in this split
                weights = {}
                break
            weights[person] = FULL if share.share == "full" else HALF

        reason = item.reason if weights else "Couldn't tell who had this"
        suggestions.append({"weights": weights, "reason": reason})
    return suggestions


def to_corrections(
    answer: CorrectionChanges, people: list[str], items: list[AssignedItem]
) -> list[Correction]:
    """Keep only changes that point at a real item and leave it with real people."""
    people_by_lowercase = {person.lower(): person for person in people}
    known_items = {(item["receipt"], item["item"]) for item in items}

    corrections: list[Correction] = []
    for change in answer.changes:
        if (change.receipt, change.item) not in known_items:
            continue

        weights = {}
        for share in change.people:
            person = people_by_lowercase.get(share.name.strip().lower())
            if person is None:
                weights = {}
                break
            weights[person] = FULL if share.share == "full" else HALF

        if weights:  # an item can't be left with nobody
            corrections.append({"receipt": change.receipt, "item": change.item, "weights": weights})
    return corrections


# --- Calling Gemini ---

READ_PROMPT = """You are reading a photo of a restaurant or shop bill from India.

List every ordered line with its name as printed (keep quantities such as "x2"), its line
total as printed, and a category: food, drink (non-alcoholic), alcohol (beer, wine, spirits,
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

For each item, decide who had it, using only the note:
- If the note says nothing that covers an item, everyone shared it.
- If the note clearly says someone did not have an item (for example "Ravi doesn't drink"
  for alcohol, or "Meena left before dessert" for desserts), list everyone else.
- A preference is not an exclusion. "Doesn't take sugar" or "doesn't like spicy food" does not
  say whether they had an item; they may have had it made their way.
- Use "half" for anyone the note says had only a little of an item.
- If the note is relevant to an item but doesn't say for sure who had it, return an empty list
  of people for it, so the user is asked. Never guess.
- Only use names from the list of people.

Return one entry per item, using the item's number as its index, with a short reason
written for the user."""


CORRECT_PROMPT = """People splitting a bill: {people}

Items, with who had each one:
{items}

The user rejected the split with this note: "{note}"

Return the changes the note asks for. For each changed item, give its receipt and item numbers
and the full list of people who had it after the change (not just the people who changed).
- Only change items the note clearly refers to.
- Only use names from the list of people.
- If the note is unclear, unrelated to who had which item, or not a real sentence, return no
  changes."""


def gemini() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        api_key=settings.gemini_api_key,
        temperature=0,
        # How much hidden reasoning the model does before answering. Reading a receipt and
        # applying a note need little, and each level up adds seconds to every call.
        thinking_level=settings.gemini_thinking_level,
    )


def read_receipt(receipt_id: str, feedback: str | None) -> Receipt:
    """Read the photo saved as uploads/<receipt_id>."""
    path = settings.uploads_dir / receipt_id
    image = base64.b64encode(path.read_bytes()).decode()
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"

    prompt = READ_PROMPT if feedback is None else f"{READ_PROMPT}\n\n{feedback}"
    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image", "base64": image, "mime_type": mime_type},
        ]
    )
    reading = gemini().with_structured_output(ReceiptReading).invoke([message])
    return reading_to_receipt(reading)


def suggest_assignments(people: list[str], note: str, items: list[LineItem]) -> list[Suggestion]:
    numbered_items = "\n".join(
        f"{index}. {item['name']} ({item['category']})" for index, item in enumerate(items)
    )
    prompt = ASSIGN_PROMPT.format(people=", ".join(people), note=note, items=numbered_items)
    answer = gemini().with_structured_output(AssignmentSuggestions).invoke(prompt)
    return to_suggestions(answer, people, len(items))


def correct_assignments(
    people: list[str], items: list[AssignedItem], note: str
) -> list[Correction]:
    listed_items = "\n".join(
        f"{item['receipt']}.{item['item']} {item['name']}: {describe_people(item['weights'])}"
        for item in items
    )
    prompt = CORRECT_PROMPT.format(people=", ".join(people), items=listed_items, note=note)
    answer = gemini().with_structured_output(CorrectionChanges).invoke(prompt)
    return to_corrections(answer, people, items)


def describe_people(weights: dict[str, int]) -> str:
    """{"Arun": FULL, "Priya": HALF} -> "Arun, Priya (half)"."""
    return ", ".join(name if weight == FULL else f"{name} (half)" for name, weight in weights.items())
