import pytest

from app.money.split import FULL, HALF
from scripts.run_split import parse_payers, parse_people

PEOPLE = ["Arun", "Priya", "Ravi"]


def test_parse_people_with_half_shares_and_any_case():
    assert parse_people("arun, Priya* ", PEOPLE) == {"weights": {"Arun": FULL, "Priya": HALF}, "by_count": False}


def test_parse_people_with_counts():
    assert parse_people("Arun=2, priya=1", PEOPLE) == {"weights": {"Arun": 2, "Priya": 1}, "by_count": True}


@pytest.mark.parametrize("answer", ["", "Rahul", "Arun,,Priya", "Arun=0", "Arun=1, Priya"])
def test_parse_people_rejects_unknown_or_empty_names(answer):
    with pytest.raises(ValueError):
        parse_people(answer, PEOPLE)


def test_parse_payers_one_name_pays_everything():
    assert parse_payers("priya", PEOPLE, 123200) == {"Priya": 123200}


def test_parse_payers_split_payment():
    assert parse_payers("Arun=1000, Priya=232", PEOPLE, 123200) == {"Arun": 100000, "Priya": 23200}


@pytest.mark.parametrize("answer", ["Rahul", "Arun=abc", "Arun=1000", "Rahul=1232"])
def test_parse_payers_rejects_bad_answers(answer):
    with pytest.raises(ValueError):
        parse_payers(answer, PEOPLE, 123200)
