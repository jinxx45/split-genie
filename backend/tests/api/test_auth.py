"""Optional Google sign-in: history, saved friends, and owner-only answers."""

from tests.agent.fakes import DINNER
from tests.api.helpers import answer, create


def sign_in(client, name="Priya"):
    return client.post("/api/auth/google", json={"credential": name})


def test_signing_in_returns_the_user_and_keeps_them_signed_in(client):
    response = sign_in(client)

    assert response.status_code == 200
    assert response.json()["user"] == {"name": "Priya", "email": "Priya@example.com", "upi_id": ""}
    assert client.get("/api/me").json()["user"]["name"] == "Priya"


def test_a_bad_google_token_is_rejected(client):
    assert sign_in(client, "bad").status_code == 401
    assert client.get("/api/me").json() == {"user": None, "friends": []}


def test_signing_out(client):
    sign_in(client)
    client.post("/api/auth/sign-out")

    assert client.get("/api/me").json()["user"] is None


def test_signed_in_splits_show_in_history_and_remember_friends(client):
    sign_in(client)
    first = create(client, people=["Priya", "Arun"]).json()
    second = create(client, people=["Priya", "Ravi", "Arun"]).json()

    history = client.get("/api/splits").json()["splits"]
    assert [split["id"] for split in history] == [second["id"], first["id"]]  # newest first
    assert history[0]["status"] == "waiting"

    friends = [friend["name"] for friend in client.get("/api/me").json()["friends"]]
    assert sorted(friends) == ["Arun", "Ravi"]  # not Priya herself


def test_history_needs_sign_in(client):
    assert client.get("/api/splits").status_code == 401


def test_only_the_owner_can_answer_a_signed_in_split(client):
    sign_in(client)
    split = create(client).json()
    assert split["can_answer"] is True

    sign_in(client, "Arun")  # someone else on the same browser
    assert client.get(f"/api/splits/{split['id']}").json()["can_answer"] is False
    response = answer(client, split["id"], DINNER)
    assert response.status_code == 403


def test_anyone_with_the_link_can_answer_a_split_started_without_signing_in(client):
    split = create(client).json()

    sign_in(client, "Arun")
    assert answer(client, split["id"], DINNER).status_code == 200


def test_saving_upi_ids(client):
    sign_in(client)

    me = client.patch("/api/me", json={"upi_id": "priya@okaxis"}).json()
    assert me["user"]["upi_id"] == "priya@okaxis"

    me = client.put("/api/me/friends", json={"name": "Arun", "upi_id": "arun@oksbi"}).json()
    assert me["friends"] == [{"name": "Arun", "upi_id": "arun@oksbi"}]

    assert client.patch("/api/me", json={"upi_id": "not a upi id"}).status_code == 422


def test_saving_upi_ids_needs_sign_in(client):
    assert client.patch("/api/me", json={"upi_id": "priya@okaxis"}).status_code == 401
