import pytest

from app.agent.receipt import apply_claims, format_rupees, item_label, strip_quantity, to_paise


@pytest.mark.parametrize(
    ("printed", "paise"),
    [
        ("600.00", 60000),
        ("₹1,232.50", 123250),
        ("Rs. 99", 9900),
        ("-0.40", -40),
        ("0.1", 10),  # exact: a float would make this 9.999…
    ],
)
def test_to_paise_reads_printed_amounts(printed, paise):
    assert to_paise(printed) == paise


def test_to_paise_rejects_text_that_is_not_an_amount():
    with pytest.raises(ValueError):
        to_paise("N/A")


def test_format_rupees():
    assert format_rupees(123205) == "₹1232.05"
    assert format_rupees(-40) == "-₹0.40"


@pytest.mark.parametrize(
    ("name", "quantity", "expected"),
    [
        ("Kingfisher x2", 2, "Kingfisher"),
        ("Kingfisher X 2", 2, "Kingfisher"),
        ("Cold Coffee ×3", 3, "Cold Coffee"),
        ("3 x Butter Naan", 3, "Butter Naan"),
        ("Kingfisher x2", 1, "Kingfisher x2"),  # only strips the quantity that was read
        ("7UP", 7, "7UP"),
        ("x2", 2, "x2"),  # never leaves an empty name
    ],
)
def test_strip_quantity(name, quantity, expected):
    assert strip_quantity(name, quantity) == expected


def test_item_label_shows_the_quantity_only_when_more_than_one():
    assert item_label({"name": "Cold Coffee", "amount_paise": 58200, "category": "drink", "quantity": 3}) == "Cold Coffee ×3"
    assert item_label({"name": "Biryani", "amount_paise": 60000, "category": "food", "quantity": 1}) == "Biryani"


def test_claims_update_the_suggestions_for_people_who_answered():
    items = [
        {"name": "Biryani", "amount_paise": 60000, "category": "food", "quantity": 1},
        {"name": "Cold Coffee", "amount_paise": 58200, "category": "drink", "quantity": 3},
        {"name": "Gulab Jamun", "amount_paise": 12000, "category": "dessert", "quantity": 1},
    ]
    everyone = {"weights": {"Priya": 2, "Arun": 2, "Ravi": 2}, "by_count": False}
    suggested = [everyone, {"weights": {}, "by_count": True}, everyone]
    # Priya (splitting the bill) hasn't answered. Ravi answered but had no dessert.
    claims = {"Arun": {0: 2, 1: 2, 2: 2}, "Ravi": {0: 1, 1: 1}}

    assert apply_claims(items, suggested, claims) == [
        {"weights": {"Priya": 2, "Arun": 2, "Ravi": 1}, "by_count": False},  # Ravi had a little
        {"weights": {"Arun": 2, "Ravi": 1}, "by_count": True},  # Arun had 2 coffees, Ravi 1
        {"weights": {"Priya": 2, "Arun": 2}, "by_count": False},  # Ravi didn't claim it: off
    ]


def test_a_claimed_count_replaces_shared_suggestions():
    items = [{"name": "Cold Coffee", "amount_paise": 58200, "category": "drink", "quantity": 3}]
    shared = [{"weights": {"Priya": 2, "Arun": 2}, "by_count": False}]

    # Full/half shares can't be mixed with counts, so Priya's shared suggestion is dropped.
    assert apply_claims(items, shared, {"Arun": {0: 3}}) == [{"weights": {"Arun": 3}, "by_count": True}]
