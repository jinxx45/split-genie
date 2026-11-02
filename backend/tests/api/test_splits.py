"""The split API end to end over HTTP, with the fake AI in place of Gemini."""

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graph import build_graph
from app.api import splits
from app.api.splits import bill_summary
from app.main import app
from tests.agent import fakes
from tests.agent.fakes import DINNER, LUNCH

PEOPLE = ["Arun", "Priya", "Ravi"]
JPEG = ("bill.jpg", b"\xff\xd8\xff fake jpeg bytes", "image/jpeg")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """An API client whose agent uses the fakes and keeps splits in memory."""
    monkeypatch.setattr(splits.settings, "uploads_dir", tmp_path / "uploads")
    graph = build_graph(
        InMemorySaver(), fakes.read_receipt, fakes.suggest_assignments, fakes.correct_assignments
    )
    app.dependency_overrides[splits.get_graph] = lambda: graph
    yield TestClient(app)
    app.dependency_overrides.clear()


def create(client, people=PEOPLE, note="Ravi doesn't drink", photos=(JPEG,)):
    return client.post(
        "/api/splits",
        data={"people": list(people), "note": note},
        files=[("photos", photo) for photo in photos],
    )


def answer(client, split_id, body):
    return client.post(f"/api/splits/{split_id}/answer", json=body)


def to_payer_step(client):
    split = create(client).json()
    answer(client, split["id"], DINNER)
    answer(client, split["id"], {"changes": {"1": {"weights": {"Arun": 2, "Ravi": 2}}}})
    return split["id"]


# --- The whole flow ---


def test_a_split_from_photo_to_payments(client):
    response = create(client)
    assert response.status_code == 201
    split = response.json()
    assert split["status"] == "waiting"
    assert split["question"]["step"] == "confirm_items"

    split = answer(client, split["id"], DINNER).json()
    assert split["question"]["step"] == "review_assignments"

    # Kingfisher x2: Arun had 1, Ravi had 1.
    by_count = {"weights": {"Arun": 1, "Ravi": 1}, "by_count": True}
    split = answer(client, split["id"], {"changes": {"1": by_count}}).json()
    assert split["question"]["step"] == "payer"

    split = answer(client, split["id"], {"paid": {"Priya": 123200}}).json()
    assert split["question"]["step"] == "approve"

    split = answer(client, split["id"], {"approved": True}).json()
    assert split["status"] == "done"
    assert split["question"] is None
    assert sum(split["result"]["shares"].values()) == 123200
    assert {p["sender"] for p in split["result"]["payments"]} == {"Arun", "Ravi"}
    assert split["result"]["title"] == "Hotel Saravana"
    assert split["result"]["total_paise"] == 123200
    assert split["result"]["paid"] == {"Priya": 123200}


def test_opening_the_link_again_shows_the_same_question(client):
    split_id = to_payer_step(client)

    reopened = client.get(f"/api/splits/{split_id}").json()

    assert reopened["status"] == "waiting"
    assert reopened["question"]["step"] == "payer"
    assert reopened["people"] == PEOPLE


def test_unknown_split_is_404(client):
    assert client.get("/api/splits/nope").status_code == 404
    assert answer(client, "nope", {}).status_code == 404


def test_answering_a_finished_split_is_409(client):
    split_id = to_payer_step(client)
    answer(client, split_id, {"paid": {"Priya": 123200}})
    answer(client, split_id, {"approved": True})

    assert answer(client, split_id, {"approved": True}).status_code == 409


# --- Creating a split ---


@pytest.mark.parametrize(
    ("people", "message"),
    [
        (["Arun"], "2 to 20 people"),
        (["Arun", "arun"], "different name"),
        (["Arun", "  "], "can't be empty"),
        (["Arun", "x" * 41], "at most 40"),
    ],
)
def test_people_are_checked(client, people, message):
    response = create(client, people=people)

    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_photos_are_checked(client, monkeypatch):
    assert "JPEG, PNG" in create(client, photos=[("bill.pdf", b"%PDF", "application/pdf")]).json()["detail"]
    assert "empty" in create(client, photos=[("bill.jpg", b"", "image/jpeg")]).json()["detail"]
    assert "1 to 5" in create(client, photos=[JPEG] * 6).json()["detail"]

    monkeypatch.setattr(splits, "MAX_PHOTO_BYTES", 10)
    assert "under" in create(client).json()["detail"]


def test_uploaded_photos_are_saved_under_our_own_names(client):
    create(client, photos=[("../../etc/passwd.jpg", b"\xff\xd8\xff", "image/jpeg")])

    saved = list(splits.settings.uploads_dir.iterdir())
    assert len(saved) == 1
    assert saved[0].name.endswith(".jpg") and "passwd" not in saved[0].name


# --- Answers are checked against the question they answer ---


def test_bad_receipt_edits_are_rejected(client):
    split_id = create(client).json()["id"]
    bad = {**DINNER, "items": [{**DINNER["items"][0], "amount_paise": -100}]}

    response = answer(client, split_id, bad)

    assert response.status_code == 422
    assert "amount_paise" in response.json()["detail"]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"9": {"weights": {"Arun": 2}}}, "no item 9"),
        ({"1": {"weights": {"Rahul": 2}}}, "Not in this split: Rahul"),
        ({"1": {"weights": {}}}, "at least one person"),
        ({"1": {"weights": {"Arun": 3}}}, "full or half"),
        ({"1": {"weights": {"Arun": 1}, "by_count": True}}, "Kingfisher ×2: 1 of 2 still need a name"),
        ({"1": {"weights": {"Arun": 2, "Ravi": 1}, "by_count": True}}, "only 2 were ordered"),
        ({"1": {"weights": {"Arun": 0}, "by_count": True}}, "changes.1.weights.Arun"),
    ],
)
def test_bad_review_answers_are_rejected_and_nothing_changes(client, changes, message):
    split_id = create(client).json()["id"]
    answer(client, split_id, DINNER)

    response = answer(client, split_id, {"changes": changes})

    assert response.status_code == 422
    assert message in response.json()["detail"]
    assert client.get(f"/api/splits/{split_id}").json()["question"]["step"] == "review_assignments"


@pytest.mark.parametrize(
    ("paid", "message"),
    [
        ({"Priya": 100}, "add up to ₹1.00, but the bill is ₹1232.00"),
        ({"Rahul": 123200}, "Not in this split: Rahul"),
        ({"Priya": 123300, "Arun": -100}, "more than zero"),
        ({}, "paid"),
    ],
)
def test_bad_payer_answers_are_rejected(client, paid, message):
    split_id = to_payer_step(client)

    response = answer(client, split_id, {"paid": paid})

    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_approval_must_be_a_real_true_or_false(client):
    split_id = to_payer_step(client)
    answer(client, split_id, {"paid": {"Priya": 123200}})

    assert answer(client, split_id, {"approved": "yes"}).status_code == 422


# --- When Gemini fails ---


def test_a_failed_step_can_be_retried(client):
    calls = []

    def flaky_reader(receipt_id, feedback):
        calls.append(receipt_id)
        if len(calls) == 1:
            raise RuntimeError("Gemini is down")
        return DINNER

    graph = build_graph(
        InMemorySaver(), flaky_reader, fakes.suggest_assignments, fakes.correct_assignments
    )
    app.dependency_overrides[splits.get_graph] = lambda: graph

    failed = create(client)
    assert failed.status_code == 502
    assert "retry" in failed.json()["detail"]

    split_id = next(iter(graph.checkpointer.storage))  # the split was saved before the failure
    assert client.get(f"/api/splits/{split_id}").json()["status"] == "failed"

    retried = client.post(f"/api/splits/{split_id}/retry").json()
    assert retried["status"] == "waiting"
    assert retried["question"]["step"] == "confirm_items"


def test_nothing_to_retry_on_a_waiting_split(client):
    split_id = create(client).json()["id"]

    assert client.post(f"/api/splits/{split_id}/retry").status_code == 409


def test_summary_covers_every_receipt():
    finished = [
        {"receipt": DINNER, "paid": {"Priya": 123200}},
        {"receipt": LUNCH, "paid": {"Priya": 20000, "Arun": 27250}},
        {"receipt": {**LUNCH, "place": ""}, "paid": {"Arun": 47250}},  # no name printed
    ]

    assert bill_summary(finished) == {
        "title": "Hotel Saravana + Murugan Idli Shop",
        "total_paise": 123200 + 47250 + 47250,
        "paid": {"Priya": 143200, "Arun": 74500},
    }
