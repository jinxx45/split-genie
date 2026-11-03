"""Groups: Friends, Trip and Flatmates, with a running tab."""

from datetime import date

import pytest

from app.api import groups as groups_module
from tests.agent.fakes import DINNER
from tests.api.helpers import answer, create

MEMBERS = ["Priya", "Arun", "Ravi"]


def sign_in(client, name="Priya"):
    client.post("/api/auth/google", json={"credential": name})


def new_group(client, kind="friends", **extra):
    sign_in(client)
    body = {"kind": kind, "name": "Lunch gang", "members": MEMBERS, "me": "Priya", **extra}
    return client.post("/api/groups", json=body)


def quick(client, group_id, amount, paid_by="Priya", weights=None, added_by="Priya", title="Cab"):
    body = {
        "title": title, "amount_paise": amount, "paid_by": paid_by,
        "weights": weights or dict.fromkeys(MEMBERS, 1), "added_by": added_by,
    }
    return client.post(f"/api/groups/{group_id}/expenses", json=body)


# --- Creating and joining ---


def test_creating_a_group_needs_sign_in(client):
    body = {"kind": "friends", "name": "Lunch gang", "members": MEMBERS, "me": "Priya"}

    assert client.post("/api/groups", json=body).status_code == 401


def test_a_new_group_shows_under_your_groups(client):
    group = new_group(client).json()

    assert group["members"] == MEMBERS and group["is_owner"]
    mine = client.get("/api/groups").json()["groups"]
    assert mine == [
        {"id": group["id"], "kind": "friends", "name": "Lunch gang", "member": "Priya", "balance_paise": 0, "closed": False}
    ]


def test_the_creator_must_be_a_member(client):
    sign_in(client)
    body = {"kind": "friends", "name": "Lunch gang", "members": MEMBERS, "me": "Rahul"}

    assert "Add yourself" in client.post("/api/groups", json=body).json()["detail"]


def test_a_signed_in_member_who_picks_their_name_gets_the_group_too(client):
    group_id = new_group(client).json()["id"]

    sign_in(client, "Arun")
    client.post(f"/api/groups/{group_id}/join", json={"member": "Arun"})

    assert client.get("/api/groups").json()["groups"][0]["member"] == "Arun"


def test_anyone_with_the_link_can_see_the_group(client):
    group_id = new_group(client).json()["id"]
    client.post("/api/auth/sign-out")

    assert client.get(f"/api/groups/{group_id}").json()["name"] == "Lunch gang"
    assert client.get("/api/groups/nope").status_code == 404


# --- The tab ---


def test_quick_expenses_update_balances_and_settle_up(client):
    group_id = new_group(client).json()["id"]

    quick(client, group_id, 90000, paid_by="Priya", added_by="Arun")  # no sign-in needed to add
    group = quick(client, group_id, 30000, paid_by="Arun", weights={"Arun": 1, "Ravi": 2}).json()

    # Priya paid 900 and owes 300; Arun paid 300 and owes 300 + 100; Ravi owes 300 + 200.
    assert group["balances"] == {"Priya": 60000, "Arun": -10000, "Ravi": -50000}
    assert sorted(group["settle_up"], key=lambda p: p["sender"]) == [
        {"sender": "Arun", "receiver": "Priya", "amount_paise": 10000},
        {"sender": "Ravi", "receiver": "Priya", "amount_paise": 50000},
    ]
    assert group["spent"] == {"Priya": 30000, "Arun": 40000, "Ravi": 50000}
    assert group["activity"][1]["added_by"] == "Arun"


def test_a_repayment_settles_balances_and_can_be_undone(client):
    group_id = new_group(client).json()["id"]
    quick(client, group_id, 90000)

    body = {"sender": "Arun", "receiver": "Priya", "amount_paise": 30000, "by": "Arun"}
    group = client.post(f"/api/groups/{group_id}/repayments", json=body).json()

    assert group["balances"]["Arun"] == 0
    repayment = next(entry for entry in group["activity"] if entry["type"] == "repayment")
    group = client.delete(f"/api/groups/{group_id}/repayments/{repayment['id']}").json()
    assert group["balances"]["Arun"] == -30000


def test_an_expense_can_be_deleted(client):
    group_id = new_group(client).json()["id"]
    expense_id = quick(client, group_id, 90000).json()["activity"][0]["id"]

    group = client.delete(f"/api/groups/{group_id}/expenses/{expense_id}").json()

    assert group["activity"] == [] and group["balances"]["Priya"] == 0


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"paid_by": "Rahul"}, "Not in this group: Rahul"),
        ({"weights": {"Arun": 1, "Rahul": 1}}, "Not in this group: Rahul"),
        ({"amount_paise": 0}, "amount_paise"),
        ({"weights": {}}, "weights"),
    ],
)
def test_bad_quick_expenses_are_rejected(client, change, message):
    group_id = new_group(client).json()["id"]
    body = {"title": "Cab", "amount_paise": 1000, "paid_by": "Priya", "weights": {"Priya": 1}, "added_by": "Priya", **change}

    response = client.post(f"/api/groups/{group_id}/expenses", json=body)

    assert response.status_code == 422 and message in response.json()["detail"]


def test_members_can_save_their_upi_id(client):
    group_id = new_group(client).json()["id"]

    group = client.put(f"/api/groups/{group_id}/upi", json={"member": "Arun", "upi_id": "arun@oksbi"}).json()

    assert group["upi_ids"] == {"Arun": "arun@oksbi"}


# --- Scanning a bill into a group ---


def test_a_scanned_bill_is_added_to_the_group_once_approved(client):
    group_id = new_group(client).json()["id"]
    split = create(client, people=MEMBERS, extra={"group_id": group_id, "added_by": "Arun"}).json()
    assert split["group"] == {"id": group_id, "name": "Lunch gang", "added_by": "Arun"}

    answer(client, split["id"], DINNER)
    answer(client, split["id"], {"changes": {"1": {"weights": {"Arun": 1, "Ravi": 1}, "by_count": True}}})
    answer(client, split["id"], {"paid": {"Priya": 123200}})
    assert client.get(f"/api/groups/{group_id}").json()["activity"] == []  # not until it's approved
    answer(client, split["id"], {"approved": True})

    group = client.get(f"/api/groups/{group_id}").json()
    [bill] = group["activity"]
    assert bill["title"] == "Saturday dinner" and bill["source"] == "bill" and bill["split_id"] == split["id"]
    assert bill["total_paise"] == 123200 and bill["paid"] == {"Priya": 123200}
    assert sum(group["balances"].values()) == 0 and group["balances"]["Priya"] > 0


def test_a_scanned_bill_must_only_have_group_members(client):
    group_id = new_group(client).json()["id"]

    response = create(client, people=["Priya", "Rahul"], extra={"group_id": group_id, "added_by": "Priya"})

    assert response.status_code == 422 and "Not in this group: Rahul" in response.json()["detail"]


# --- Trips ---


def test_a_trip_keeps_its_dates_and_can_be_ended_and_reopened(client):
    trip = new_group(client, kind="trip", start_date="2026-12-12", end_date="2026-12-15").json()
    assert (trip["start_date"], trip["end_date"]) == ("2026-12-12", "2026-12-15")
    quick(client, trip["id"], 90000)

    ended = client.put(f"/api/groups/{trip['id']}/closed", json={"closed": True}).json()

    assert ended["closed"]
    assert quick(client, trip["id"], 1000).status_code == 409  # no new expenses
    body = {"sender": "Arun", "receiver": "Priya", "amount_paise": 30000, "by": "Arun"}
    assert client.post(f"/api/groups/{trip['id']}/repayments", json=body).status_code == 201  # settling is fine
    assert not client.put(f"/api/groups/{trip['id']}/closed", json={"closed": False}).json()["closed"]


def test_only_the_trip_creator_can_end_it(client):
    trip_id = new_group(client, kind="trip").json()["id"]
    sign_in(client, "Arun")

    assert client.put(f"/api/groups/{trip_id}/closed", json={"closed": True}).status_code == 403


def test_a_trip_cant_end_before_it_starts(client):
    response = new_group(client, kind="trip", start_date="2026-12-15", end_date="2026-12-12")

    assert "can't end before it starts" in response.json()["detail"]


# --- Flatmates ---


@pytest.fixture
def on(monkeypatch):
    """Pretend today is a given date (Indian time)."""
    def set_today(day: date):
        monkeypatch.setattr(groups_module, "today_ist", lambda: day)
    return set_today


def test_rent_is_added_every_month_on_its_day(client, on):
    on(date(2026, 11, 3))
    flat_id = new_group(client, kind="flat").json()["id"]
    rent = {"title": "Rent", "amount_paise": 3000000, "paid_by": "Priya", "weights": {"Priya": 2, "Arun": 1, "Ravi": 1}, "day_of_month": 1}

    flat = client.post(f"/api/groups/{flat_id}/recurring", json=rent).json()
    assert [e["title"] for e in flat["activity"]] == ["Rent, Nov 2026"]  # the 1st has passed: added now
    assert flat["activity"][0]["owed"] == {"Priya": 1500000, "Arun": 750000, "Ravi": 750000}

    on(date(2027, 1, 1))
    titles = sorted(e["title"] for e in client.get(f"/api/groups/{flat_id}").json()["activity"])
    assert titles == ["Rent, Dec 2026", "Rent, Jan 2027", "Rent, Nov 2026"]  # each month once
    assert len(client.get(f"/api/groups/{flat_id}").json()["activity"]) == 3  # repeating adds nothing


def test_a_changing_bill_asks_for_each_months_amount(client, on):
    on(date(2026, 11, 3))
    flat_id = new_group(client, kind="flat").json()["id"]
    power = {"title": "Electricity", "paid_by": "Arun", "weights": dict.fromkeys(MEMBERS, 1), "day_of_month": 10}
    flat = client.post(f"/api/groups/{flat_id}/recurring", json=power).json()
    assert flat["due"] == []  # due on the 10th

    on(date(2026, 11, 12))
    flat = client.get(f"/api/groups/{flat_id}").json()
    [due] = flat["due"]
    assert (due["title"], due["month"], due["label"], due["paid_by"]) == ("Electricity", "2026-11", "Nov 2026", "Arun")

    url = f"/api/groups/{flat_id}/recurring/{due['recurring_id']}/months/2026-11"
    flat = client.put(url, json={"amount_paise": 240000, "by": "Arun"}).json()
    assert flat["due"] == []
    assert flat["activity"][0]["title"] == "Electricity, Nov 2026" and flat["balances"]["Arun"] == 160000
    assert client.put(url.replace("2026-11", "2026-12"), json={"amount_paise": 1, "by": "Arun"}).status_code == 422


def test_flatmates_see_each_months_totals(client, on):
    on(date(2026, 11, 3))
    flat_id = new_group(client, kind="flat").json()["id"]
    quick(client, flat_id, 90000, title="Groceries")

    [month] = client.get(f"/api/groups/{flat_id}").json()["months"]

    assert month == {"month": "2026-11", "label": "Nov 2026", "total_paise": 90000,
                     "owed": {"Priya": 30000, "Arun": 30000, "Ravi": 30000}}


def test_a_stopped_bill_isnt_added_again(client, on):
    on(date(2026, 11, 3))
    flat_id = new_group(client, kind="flat").json()["id"]
    rent = {"title": "Rent", "amount_paise": 3000000, "paid_by": "Priya", "weights": {"Priya": 1}, "day_of_month": 1}
    bill_id = client.post(f"/api/groups/{flat_id}/recurring", json=rent).json()["recurring"][0]["id"]

    client.delete(f"/api/groups/{flat_id}/recurring/{bill_id}")
    on(date(2026, 12, 5))

    flat = client.get(f"/api/groups/{flat_id}").json()
    assert flat["recurring"] == [] and [e["title"] for e in flat["activity"]] == ["Rent, Nov 2026"]


def test_monthly_bills_are_only_for_flatmates(client):
    group_id = new_group(client).json()["id"]
    rent = {"title": "Rent", "amount_paise": 1000, "paid_by": "Priya", "weights": {"Priya": 1}, "day_of_month": 1}

    assert "flatmates" in client.post(f"/api/groups/{group_id}/recurring", json=rent).json()["detail"]
