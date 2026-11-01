import pytest

from app.agent.receipt import format_rupees, to_paise


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
