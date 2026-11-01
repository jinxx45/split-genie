"""What the API accepts from the browser, and the checks applied before anything reaches the agent.

Pydantic checks each answer's shape and limits. The functions below add the checks that need
the split itself: are these names in the split, does this item exist, does the money add up.
"""

from typing import Annotated

from fastapi import HTTPException
from pydantic import BaseModel, Field, StrictBool

from app.agent.receipt import Category, LineItem, assignment_problem, format_rupees

MAX_PEOPLE = 20
MAX_NAME_LENGTH = 40
MAX_NOTE_LENGTH = 500
MAX_PHOTOS = 5
MAX_PHOTO_BYTES = 10 * 1024 * 1024  # 10 MB
PHOTO_TYPES = {  # what Gemini can read -> the file extension we save it with
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}
MAX_AMOUNT_PAISE = 10_000_000  # ₹1,00,000 per line, far above any real bill line
MAX_QUANTITY = 999


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    amount_paise: int = Field(ge=0, le=MAX_AMOUNT_PAISE)
    category: Category
    quantity: int = Field(default=1, ge=1, le=MAX_QUANTITY)


class ReceiptIn(BaseModel):
    """Answer to "check the items": the receipt, with any fixes."""

    place: str = Field(default="", max_length=100)
    items: list[ItemIn] = Field(min_length=1, max_length=200)
    tax_paise: int = Field(ge=-MAX_AMOUNT_PAISE, le=MAX_AMOUNT_PAISE)  # negative: a discount
    service_charge_paise: int = Field(ge=0, le=MAX_AMOUNT_PAISE)
    printed_total_paise: int = Field(ge=0, le=MAX_AMOUNT_PAISE)


class AssignmentIn(BaseModel):
    """Who had one item: FULL (2) or HALF (1) shares, or with by_count, how many each had."""

    weights: dict[str, Annotated[int, Field(ge=1, le=MAX_QUANTITY)]]
    by_count: bool = False


class ReviewIn(BaseModel):
    """Answer to "who had what": only the items the user changed."""

    changes: dict[int, AssignmentIn]  # item index -> who had it


class PayerIn(BaseModel):
    """Answer to "who paid"."""

    paid: dict[str, int] = Field(min_length=1)


class ApprovalIn(BaseModel):
    """Answer to the final approval. The agent itself checks the note's wording."""

    approved: StrictBool  # StrictBool: only true/false, not "yes" or 1
    note: str | None = Field(default=None, max_length=2 * MAX_NOTE_LENGTH)


def reject(message: str) -> HTTPException:
    """422 Unprocessable Content: the request was understood but its data can't be used."""
    return HTTPException(status_code=422, detail=message)


def clean_people(names: list[str]) -> list[str]:
    people = [name.strip() for name in names]
    if any(not name for name in people):
        raise reject("Names can't be empty.")
    if any(len(name) > MAX_NAME_LENGTH for name in people):
        raise reject(f"Names must be at most {MAX_NAME_LENGTH} characters.")
    if len({name.lower() for name in people}) != len(people):
        raise reject("Each person must have a different name.")
    if not 2 <= len(people) <= MAX_PEOPLE:
        raise reject(f"A split needs 2 to {MAX_PEOPLE} people.")
    return people


def check_review(review: ReviewIn, people: list[str], items: list[LineItem]) -> None:
    for index, assignment in review.changes.items():
        if not 0 <= index < len(items):
            raise reject(f"There is no item {index}.")
        unknown = [name for name in assignment.weights if name not in people]
        if unknown:
            raise reject(f"Not in this split: {', '.join(unknown)}.")
        problem = assignment_problem(assignment.model_dump(), items[index]["quantity"])
        if problem:
            raise reject(f"{items[index]['name']}: {problem}")


def check_payers(payer: PayerIn, people: list[str], total_paise: int) -> None:
    unknown = [name for name in payer.paid if name not in people]
    if unknown:
        raise reject(f"Not in this split: {', '.join(unknown)}.")
    if any(amount <= 0 for amount in payer.paid.values()):
        raise reject("Each amount paid must be more than zero.")
    paid = sum(payer.paid.values())
    if paid != total_paise:
        raise reject(f"Payments add up to {format_rupees(paid)}, but the bill is {format_rupees(total_paise)}.")
