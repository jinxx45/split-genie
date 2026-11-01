"""Tests for the Gemini step, without calling Gemini: the conversions, plus a fake model."""

from app.agent import llm
from app.agent.llm import (
    AssignmentSuggestions,
    ItemSuggestion,
    PersonShare,
    ReadCharge,
    ReadLine,
    ReceiptReading,
    reading_to_receipt,
    to_suggestions,
)
from app.agent.receipt import totals_match
from app.money.split import FULL, HALF

PEOPLE = ["Arun", "Priya", "Ravi"]


def test_reading_is_converted_to_paise_and_charges_are_grouped():
    reading = ReceiptReading(
        items=[
            ReadLine(name="Chicken Biryani", amount="600.00", category="food"),
            ReadLine(name="Kingfisher x2", amount="400.00", category="alcohol"),
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
    }
    assert receipt["tax_paise"] == 2500 + 2500 - 40
    assert receipt["service_charge_paise"] == 5000
    assert totals_match(receipt)


def test_unreadable_amount_counts_as_zero_so_totals_do_not_match():
    reading = ReceiptReading(
        items=[ReadLine(name="Dosa", amount="??", category="food")],
        charges=[],
        total="120.00",
    )

    assert not totals_match(reading_to_receipt(reading))


def suggestion(index, *shares, reason="from the note"):
    return ItemSuggestion(
        index=index,
        people=[PersonShare(name=name, share=share) for name, share in shares],
        reason=reason,
    )


def test_suggestions_map_names_and_shares():
    answer = AssignmentSuggestions(
        items=[
            suggestion(0, ("arun", "full"), ("PRIYA ", "half"), reason="Priya barely ate"),
            suggestion(1, ("Arun", "full"), ("Priya", "full"), reason="Ravi doesn't drink"),
        ]
    )

    result = to_suggestions(answer, PEOPLE, item_count=2)

    assert result[0] == {"weights": {"Arun": FULL, "Priya": HALF}, "reason": "Priya barely ate"}
    assert result[1]["weights"] == {"Arun": FULL, "Priya": FULL}


def test_unknown_names_and_missing_items_become_questions():
    answer = AssignmentSuggestions(items=[suggestion(0, ("Rahul", "full"))])

    result = to_suggestions(answer, PEOPLE, item_count=2)

    assert result[0]["weights"] == {}  # Rahul isn't in this split
    assert result[1]["weights"] == {}  # Gemini skipped item 1


def test_empty_people_list_means_ask_the_user():
    answer = AssignmentSuggestions(items=[suggestion(0)])

    assert to_suggestions(answer, PEOPLE, item_count=1)[0]["weights"] == {}


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
    fake = FakeGemini(ReceiptReading(items=[], charges=[], total="0"))
    monkeypatch.setattr(llm, "gemini", lambda: fake)

    llm.read_receipt("r1.png", feedback="Your last reading added up to ₹1.00")

    text_part, image_part = fake.sent[0].content
    assert text_part["text"].endswith("Your last reading added up to ₹1.00")
    assert image_part["mime_type"] == "image/png"


def test_suggest_assignments_never_sends_prices(monkeypatch):
    fake = FakeGemini(AssignmentSuggestions(items=[]))
    monkeypatch.setattr(llm, "gemini", lambda: fake)
    items = [{"name": "Kingfisher x2", "amount_paise": 40000, "category": "alcohol"}]

    llm.suggest_assignments(PEOPLE, "Ravi doesn't drink", items)

    assert "Kingfisher x2 (alcohol)" in fake.sent
    assert "400" not in fake.sent
