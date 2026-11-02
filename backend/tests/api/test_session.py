"""The signed sign-in cookie."""

from app.api import session

NOW = 1_800_000_000


def test_a_signed_cookie_gives_back_the_user_id():
    assert session.read(session.sign("google-123", now=NOW), now=NOW + 60) == "google-123"


def test_an_edited_cookie_is_rejected():
    cookie = session.sign("google-123", now=NOW)
    payload, signature = cookie.rsplit(".", 1)
    forged = session.sign("google-999", now=NOW).rsplit(".", 1)[0]  # someone else's id...

    assert session.read(f"{forged}.{signature}", now=NOW) is None  # ...with the old signature
    assert session.read(f"{payload}.{'0' * len(signature)}", now=NOW) is None


def test_an_expired_cookie_is_rejected():
    cookie = session.sign("google-123", now=NOW)

    assert session.read(cookie, now=NOW + session.MAX_AGE_SECONDS + 1) is None


def test_missing_or_malformed_cookies_are_rejected():
    for cookie in (None, "", "no-dot", "abc.def"):
        assert session.read(cookie, now=NOW) is None
