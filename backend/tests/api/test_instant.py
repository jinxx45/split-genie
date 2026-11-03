"""Instant split: one amount, no photo. Saved like a scanned bill and done straight away."""

import pytest

PEOPLE = ["Priya", "Arun", "Ravi"]


def instant(client, amount=120000, paid_by="Priya", shares=None, people=PEOPLE, name="Cab to Baga"):
    body = {
        "name": name, "amount_paise": amount, "people": people, "paid_by": paid_by,
        "shares": dict.fromkeys(people, 1) if shares is None else shares,
    }
    return client.post("/api/splits/instant", json=body)


def test_an_equal_split_is_done_straight_away(client):
    response = instant(client)

    assert response.status_code == 201
    split = response.json()
    assert (split["status"], split["name"]) == ("done", "Cab to Baga")
    result = split["result"]
    assert result["total_paise"] == 120000 and result["paid"] == {"Priya": 120000}
    assert result["shares"] == {"Priya": 40000, "Arun": 40000, "Ravi": 40000}
    assert sorted((p["sender"], p["receiver"], p["amount_paise"]) for p in result["payments"]) == [
        ("Arun", "Priya", 40000), ("Ravi", "Priya", 40000),
    ]


def test_it_opens_again_from_its_link(client):
    split_id = instant(client).json()["id"]

    assert client.get(f"/api/splits/{split_id}").json()["status"] == "done"


def test_uneven_shares_are_in_proportion_and_never_called_half(client):
    result = instant(client, amount=120000, shares={"Priya": 1, "Arun": 1, "Ravi": 2}).json()["result"]

    assert result["shares"] == {"Priya": 30000, "Arun": 30000, "Ravi": 60000}
    assert not any(item["half"] for part in result["breakdown"].values() for item in part["items"])


def test_odd_paise_still_add_up_to_the_total(client):
    result = instant(client, amount=100).json()["result"]

    assert sum(result["shares"].values()) == 100


def test_the_payer_can_pay_for_others_without_a_share(client):
    result = instant(client, amount=50000, shares={"Arun": 1, "Ravi": 1}).json()["result"]

    assert result["shares"] == {"Arun": 25000, "Ravi": 25000}
    assert len(result["payments"]) == 2


def test_payments_can_be_marked_paid(client):
    split_id = instant(client).json()["id"]

    body = {"sender": "Arun", "receiver": "Priya", "paid": True, "by": "Arun"}
    payments = client.post(f"/api/splits/{split_id}/payments", json=body).json()["result"]["payments"]

    assert next(p for p in payments if p["sender"] == "Arun")["marked_paid_by"] == "Arun"


def test_it_shows_in_the_signed_in_users_history(client):
    client.post("/api/auth/google", json={"credential": "Priya"})
    split_id = instant(client).json()["id"]

    [split] = client.get("/api/splits").json()["splits"]
    assert (split["id"], split["name"], split["total_paise"]) == (split_id, "Cab to Baga", 120000)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"paid_by": "Rahul"}, "Not in this split: Rahul"),
        ({"shares": {"Priya": 1, "Rahul": 1}}, "Not in this split: Rahul"),
        ({"shares": {"Priya": 0}}, "shares"),
        ({"shares": {"Priya": 10}}, "shares"),
        ({"shares": {}}, "shares"),
        ({"amount": 0}, "amount_paise"),
        ({"name": "  "}, "Give the split a name"),
        ({"people": ["Priya"], "shares": {"Priya": 1}}, "2 to 20 people"),
    ],
)
def test_bad_instant_splits_are_rejected(client, change, message):
    response = instant(client, **change)

    assert response.status_code == 422 and message in response.json()["detail"]
