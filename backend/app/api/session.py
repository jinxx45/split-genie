"""The sign-in cookie: the user's id, signed so it can't be forged or edited. Standard library only.

The cookie holds "<user id>|<when it was issued>" plus an HMAC signature of that text, made with
SESSION_SECRET. Without the secret, nobody can produce a valid signature, so changing the user id
in the cookie makes it invalid.
"""

import base64
import hashlib
import hmac
import logging
import secrets
import time

from app.config import settings

COOKIE_NAME = "split_genie_session"
MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days

if not settings.session_secret:
    logging.getLogger("split_genie.api").warning(
        "SESSION_SECRET is not set: everyone is signed out when the server restarts"
    )
SECRET = (settings.session_secret or secrets.token_hex(32)).encode()


def sign(user_id: str, now: float | None = None) -> str:
    """The cookie value for a signed-in user."""
    issued_at = int(time.time() if now is None else now)
    payload = base64.urlsafe_b64encode(f"{user_id}|{issued_at}".encode()).decode()
    return f"{payload}.{signature(payload)}"


def read(cookie: str | None, now: float | None = None) -> str | None:
    """The user id in a cookie, or None if it's missing, edited, signed with another secret, or
    older than MAX_AGE_SECONDS."""
    if not cookie or "." not in cookie:
        return None
    payload, given = cookie.rsplit(".", 1)
    # compare_digest takes the same time however many characters match, so an attacker can't
    # guess a valid signature one character at a time by timing the responses.
    if not hmac.compare_digest(given, signature(payload)):
        return None
    try:
        user_id, issued_at = base64.urlsafe_b64decode(payload).decode().rsplit("|", 1)
        age = (time.time() if now is None else now) - int(issued_at)
    except ValueError:  # not base64 or not "id|number": can't happen with a valid signature
        return None
    return user_id if 0 <= age <= MAX_AGE_SECONDS else None


def signature(payload: str) -> str:
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()
