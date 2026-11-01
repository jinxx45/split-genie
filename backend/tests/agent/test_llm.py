"""Tests for the Gemini step, without calling Gemini: the conversions, plus a fake model."""

from app.agent import llm
from app.agent.llm import (
    AssignmentSuggestions,
    CorrectionChanges,
    ItemChange,
    ItemSuggestion,
    PersonShare,
    ReadCharge,
    ReadLine,
    ReceiptReading,
    reading_to_receipt,
    to_corrections,
    to_suggestions,
)
from app.agent.receipt import totals_match
from app.money.split import FULL, HALF

PEOPLE = ["Arun", "Priya", "Ravi"]


def test_reading_is_converted_to_paise_and_charges_are_grouped():
    reading = ReceiptReading(
        place=" Hotel Saravana ",
        items=[
            ReadLine(name="Chicken Biryani", amount="600.00", quantity=1, category="food"),
            ReadLine(name="Kingfisher x2", amount="400.00", quantity=2, category="alcohol"),
        ],
        charges=[
            ReadCharge(label="CGST 2.5%", amount="25.00", kind="tax"),
            ReadCharge(label="SGST 2.5%", amount="25.00", kind="tax"),
            ReadCharge(label="Service Charge", amount="50.00", kind="service_charge"),
            ReadCharge(label="Round Off", amount="-0.40", kind="adjustment"),
        ],
        total="₹1,099.60",
    )

    receipt = reading_to_receipt(reading)

    assert receipt["items"][1] == {
        "name": "Kingfisher x2",
        "amount_paise": 40000,
        "category": "alcohol",
        "quantity": 2,
    }
    assert receipt["tax_paise"] == 2500 + 2500 - 40
    assert receipt["service_charge_paise"] == 5000
    assert receipt["place"] == "Hotel Saravana"
    assert totals_match(receipt)


def test_unreadable_amount_counts_as_zero_so_totals_do_not_match():
    reading = ReceiptReading(
        place="",
        items=[ReadLine(name="Dosa", amount="??", quantity=0, category="food")],
        charges=[],
        total="120.00",
    )

    receipt = reading_to_receipt(reading)
    assert not totals_match(receipt)
    assert receipt["items"][0]["quantity"] == 1  # a misread quantity of 0 becomes 1


def suggestion(index, *shares, reason="from the note"):
    """shares: (name, "full"/"half") or (name, "full", count)."""
    return ItemSuggestion(index=index, people=[person_share(*share) for share in shares], reason=reason)


def person_share(name, share, count=0):
    return PersonShare(name=name, share=share, count=count)


ITEMS = [
    {"name": "Chicken Biryani", "amount_paise": 60000, "category": "food", "quantity": 1},
    {"name": "Kingfisher x2", "amount_paise": 40000, "category": "alcohol", "quantity": 2},
    {"name": "Filter Coffee x1", "amount_paise": 9500, "category": "drink", "quantity": 1},
]


def test_items_the_note_is_about_use_gemini_answer():
    answer = AssignmentSuggestions(
        exceptions=[
            suggestion(0, ("arun", "full"), ("PRIYA ", "half"), reason="Priya barely ate"),
            suggestion(1, ("Arun", "full"), ("Priya", "full"), reason="Ravi doesn't drink"),
        ]
    )

    result = to_suggestions(answer, PEOPLE, ITEMS)

    assert result[0] == {"weights": {"Arun": FULL, "Priya": HALF}, "by_count": False, "reason": "Priya barely ate"}
    assert result[1]["weights"] == {"Arun": FULL, "Priya": FULL}


def test_items_left_out_get_the_default_food_shared_drinks_asked():
    result = to_suggestions(AssignmentSuggestions(exceptions=[]), PEOPLE, ITEMS)

    assert result[0]["weights"] == {"Arun": FULL, "Priya": FULL, "Ravi": FULL}
    assert result[1] == {"weights": {}, "by_count": True, "reason": "Drinks are usually one each: who had how many?"}
    assert result[2]["weights"] == {} and not result[2]["by_count"]  # a single drink: ask who


def test_unknown_names_become_questions():
    answer = AssignmentSuggestions(exceptions=[suggestion(0, ("Rahul", "full"))])

    result = to_suggestions(answer, PEOPLE, ITEMS)

    assert result[0] == {"weights": {}, "by_count": False, "reason": "Not sure who had this"}


def test_counts_from_the_note_split_the_item_by_count_and_leave_the_rest_to_ask():
    answer = AssignmentSuggestions(exceptions=[suggestion(1, ("Priya", "full", 1), ("Arun", "full"))])

    result = to_suggestions(answer, PEOPLE, ITEMS)

    # "Priya had one Kingfisher": Priya 1 of 2; Arun has no count, so the other one is asked.
    assert result[1] == {"weights": {"Priya": 1}, "by_count": True, "reason": "from the note"}


def test_counts_above_the_quantity_are_not_trusted():
    answer = AssignmentSuggestions(exceptions=[suggestion(1, ("Priya", "full", 2), ("Arun", "full", 1))])

    assert to_suggestions(answer, PEOPLE, ITEMS)[1] == {
        "weights": {},
        "by_count": True,
        "reason": "Not sure who had how many",
    }


def test_empty_people_list_means_ask_the_user_with_gemini_reason():
    answer = AssignmentSuggestions(exceptions=[suggestion(0, reason="Note is unclear")])

    assert to_suggestions(answer, PEOPLE, ITEMS)[0] == {"weights": {}, "by_count": False, "reason": "Note is unclear"}


class FakeGemini:
    """Records what would be sent to Gemini and returns a fixed answer."""

    def __init__(self, answer):
        self.answer = answer
        self.sent = None

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        self.sent = messages
        return self.answer


def test_read_receipt_sends_the_photo_and_any_feedback(tmp_path, monkeypatch):
    (tmp_path / "r1.png").write_bytes(b"fake image bytes")
    monkeypatch.setattr(llm.settings, "uploads_dir", tmp_path)
    fake = FakeGemini(ReceiptReading(place="", items=[], charges=[], total="0"))
    monkeypatch.setattr(llm, "gemini", lambda: fake)

    llm.read_receipt("r1.png", feedback="Your last reading added up to ₹1.00")

    text_part, image_part = fake.sent[0].content
    assert text_part["text"].endswith("Your last reading added up to ₹1.00")
    assert image_part["mime_type"] == "image/png"


def test_suggest_assignments_never_sends_prices(monkeypatch):
    fake = FakeGemini(AssignmentSuggestions(exceptions=[]))
    monkeypatch.setattr(llm, "gemini", lambda: fake)
    items = [{"name": "Kingfisher x2", "amount_paise": 40000, "category": "alcohol", "quantity": 2}]

    llm.suggest_assignments(PEOPLE, "Ravi doesn't drink", items)

    assert "Kingfisher x2 (alcohol, quantity 2)" in fake.sent
    assert "400" not in fake.sent


SHARED = {"weights": {"Arun": FULL, "Priya": FULL}, "by_count": False}
ASSIGNED = [
    {"receipt": 0, "item": 0, "name": "Chicken Biryani", "quantity": 1, **SHARED},
    {"receipt": 0, "item": 1, "name": "Gulab Jamun", "quantity": 1, **SHARED},
    {"receipt": 0, "item": 2, "name": "Cold Coffee x3", "quantity": 3, **SHARED},
]


def change(receipt, item, *shares):
    return ItemChange(
        receipt=receipt,
        item=item,
        people=[person_share(*share) for share in shares],
    )


def test_corrections_keep_valid_changes():
    answer = CorrectionChanges(
        changes=[
            change(0, 1, ("arun", "full")),
            change(0, 2, ("Priya", "full", 1), ("Arun", "full", 2)),  # counts add up to 3
        ]
    )

    assert to_corrections(answer, PEOPLE, ASSIGNED) == [
        {"receipt": 0, "item": 1, "weights": {"Arun": FULL}, "by_count": False},
        {"receipt": 0, "item": 2, "weights": {"Priya": 1, "Arun": 2}, "by_count": True},
    ]


def test_corrections_drop_unknown_items_unknown_names_and_empty_items():
    answer = CorrectionChanges(
        changes=[
            change(0, 7, ("Arun", "full")),  # no item 7
            change(3, 0, ("Arun", "full")),  # no receipt 3
            change(0, 0, ("Rahul", "full")),  # not in this split
            change(0, 1),  # would leave the item with nobody
            change(0, 2, ("Priya", "full", 1)),  # only 1 of the 3 coffees has a name
        ]
    )

    assert to_corrections(answer, PEOPLE, ASSIGNED) == []


def test_correct_assignments_lists_items_with_ids_and_people_but_no_prices(monkeypatch):
    fake = FakeGemini(CorrectionChanges(changes=[]))
    monkeypatch.setattr(llm, "gemini", lambda: fake)
    items = [
        {"receipt": 0, "item": 1, "name": "Gulab Jamun", "quantity": 1,
         "weights": {"Arun": FULL, "Priya": HALF}, "by_count": False},
        {"receipt": 0, "item": 2, "name": "Cold Coffee x3", "quantity": 3,
         "weights": {"Arun": 2, "Priya": 1}, "by_count": True},
    ]

    llm.correct_assignments(PEOPLE, items, "Priya didn't have dessert")

    assert "0.1 Gulab Jamun (quantity 1): Arun, Priya (half)" in fake.sent
    assert "0.2 Cold Coffee x3 (quantity 3): Arun had 2, Priya had 1" in fake.sent
    assert "Priya didn't have dessert" in fake.sent
