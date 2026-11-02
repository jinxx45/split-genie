import pytest

from app.agent.receipt import format_rupees, item_label, strip_quantity, to_paise


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
