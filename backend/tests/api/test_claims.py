"""Friends claiming what they had, while the split waits on "who had what"."""

from tests.agent.fakes import DINNER
from tests.api.helpers import answer, create


def at_review(client) -> str:
    split_id = create(client).json()["id"]
    answer(client, split_id, DINNER)  # Biryani, Kingfisher ×2, Gulab Jamun
    return split_id


def claim(client, split_id, person, items):
    return client.post(f"/api/splits/{split_id}/claims", json={"person": person, "items": items})


def test_claims_are_shown_to_the_splitter_with_what_they_add_up_to(client):
    split_id = at_review(client)

    claim(client, split_id, "Arun", {"0": 2, "1": 1})
    question = claim(client, split_id, "Ravi", {"0": 1, "1": 1}).json()["question"]

    assert question["claims"] == {"Arun": {"0": 2, "1": 1}, "Ravi": {"0": 1, "1": 1}}
    assert question["claimed"] == [
        {"weights": {"Priya": 2, "Arun": 2, "Ravi": 1}, "by_count": False},  # Priya hasn't answered
        {"weights": {"Arun": 1, "Ravi": 1}, "by_count": True},  # one Kingfisher each
        {"weights": {"Priya": 2}, "by_count": False},  # both answered without the gulab jamun
    ]


def test_a_friend_can_change_their_answer_or_say_they_had_nothing(client):
    split_id = at_review(client)
    claim(client, split_id, "Arun", {"0": 2})

    question = claim(client, split_id, "Arun", {}).json()["question"]

    assert question["claims"] == {"Arun": {}}  # answered: had none of it
    assert all("Arun" not in assignment["weights"] for assignment in question["claimed"])


def test_claims_dont_change_the_split_until_the_splitter_uses_them(client):
    split_id = at_review(client)
    claim(client, split_id, "Arun", {"2": 2})

    items = client.get(f"/api/splits/{split_id}").json()["question"]["items"]

    assert items[2]["suggested"]["weights"] == {"Arun": 2, "Priya": 2, "Ravi": 2}  # unchanged


def test_claims_are_only_taken_while_asking_who_had_what(client):
    split_id = create(client).json()["id"]  # still at "is this the bill?"

    assert claim(client, split_id, "Arun", {"0": 2}).status_code == 409


def test_bad_claims_are_rejected(client):
    split_id = at_review(client)

    assert "Not in this split" in claim(client, split_id, "Rahul", {}).json()["detail"]
    assert "no item 9" in claim(client, split_id, "Arun", {"9": 2}).json()["detail"]
    assert "had a little" in claim(client, split_id, "Arun", {"0": 3}).json()["detail"]
    assert "only 2 were ordered" in claim(client, split_id, "Arun", {"1": 3}).json()["detail"]
