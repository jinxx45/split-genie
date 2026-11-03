"""Small helpers shared by the API tests."""

PEOPLE = ["Arun", "Priya", "Ravi"]
JPEG = ("bill.jpg", b"\xff\xd8\xff fake jpeg bytes", "image/jpeg")


def fake_google(credential: str) -> dict:
    """Stands in for Google's token check: the "token" is just the account's name."""
    if credential == "bad":
        raise ValueError("invalid token")
    return {
        "sub": f"google-{credential}",
        "email": f"{credential}@example.com",
        "email_verified": True,
        "given_name": credential,
    }


def create(client, people=PEOPLE, note="Ravi doesn't drink", photos=(JPEG,), name="Saturday dinner", extra=None):
    """Start a split. `extra`: more form fields, e.g. a group_id."""
    return client.post(
        "/api/splits",
        data={"name": name, "people": list(people), "note": note, **(extra or {})},
        files=[("photos", photo) for photo in photos],
    )


def answer(client, split_id, body):
    return client.post(f"/api/splits/{split_id}/answer", json=body)
