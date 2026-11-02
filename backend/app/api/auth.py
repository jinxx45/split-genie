"""Optional Google sign-in, and the signed-in user's own details: UPI ID and saved friends.

The browser gets a signed Google ID token from Google's button and sends it here. We check it
with Google's public keys, then remember the user in a signed session cookie.
"""

from collections.abc import Callable
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel, Field

from app.api.accounts import AccountStore, User
from app.api.schemas import MAX_NAME_LENGTH, UPI_ID_PATTERN
from app.config import settings

router = APIRouter(prefix="/api", tags=["account"])

VerifyToken = Callable[[str], dict]
"""Google ID token -> its claims (sub, email, given_name...). Raises ValueError if it isn't valid."""


def verify_google_token(credential: str) -> dict:
    """Checks the token's signature, expiry, and that it was issued for this app's client ID."""
    return id_token.verify_oauth2_token(credential, google_requests.Request(), settings.google_client_id)


def get_verifier() -> VerifyToken:
    return verify_google_token  # tests replace this with a fake


@lru_cache
def get_accounts() -> AccountStore:
    return AccountStore(settings.database_path)


def current_user(request: Request, accounts: AccountStore = Depends(get_accounts)) -> User | None:
    """The signed-in user, or None. Signing in is optional, so most endpoints accept None."""
    user_id = request.session.get("user_id")
    return accounts.user(user_id) if user_id else None


def require_user(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in first.")
    return user


# --- What the browser sends ---


class GoogleSignInIn(BaseModel):
    credential: str = Field(min_length=1, max_length=4096)


class ProfileIn(BaseModel):
    upi_id: str = Field(pattern=UPI_ID_PATTERN)


class FriendIn(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    upi_id: str = Field(pattern=UPI_ID_PATTERN)


# --- Endpoints ---


@router.get("/auth/config")
def auth_config() -> dict:
    """The Google client ID for the sign-in button; empty means sign-in isn't set up."""
    return {"google_client_id": settings.google_client_id}


@router.post("/auth/google")
def sign_in(
    body: GoogleSignInIn,
    request: Request,
    accounts: AccountStore = Depends(get_accounts),
    verify: VerifyToken = Depends(get_verifier),
) -> dict:
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google sign-in isn't set up on this server.")
    try:
        claims = verify(body.credential)
    except ValueError:
        raise HTTPException(status_code=401, detail="Couldn't sign you in with Google. Please try again.") from None
    if not claims.get("email_verified"):
        raise HTTPException(status_code=401, detail="Your Google email isn't verified.")

    name = claims.get("given_name") or claims.get("name") or claims["email"].split("@")[0]
    user = accounts.sign_in(claims["sub"], claims["email"], name.strip()[:MAX_NAME_LENGTH])
    request.session["user_id"] = user.id
    return describe_me(user, accounts)


@router.post("/auth/sign-out")
def sign_out(request: Request) -> dict:
    request.session.clear()
    return {"user": None, "friends": []}


@router.get("/me")
def me(user: User | None = Depends(current_user), accounts: AccountStore = Depends(get_accounts)) -> dict:
    return describe_me(user, accounts)


@router.patch("/me")
def update_me(
    profile: ProfileIn, user: User = Depends(require_user), accounts: AccountStore = Depends(get_accounts)
) -> dict:
    accounts.set_upi_id(user.id, profile.upi_id)
    return describe_me(accounts.user(user.id), accounts)


@router.put("/me/friends")
def save_friend(
    friend: FriendIn, user: User = Depends(require_user), accounts: AccountStore = Depends(get_accounts)
) -> dict:
    accounts.set_friend_upi_id(user.id, friend.name.strip(), friend.upi_id)
    return describe_me(user, accounts)


def describe_me(user: User | None, accounts: AccountStore) -> dict:
    if user is None:
        return {"user": None, "friends": []}
    return {
        "user": {"name": user.name, "email": user.email, "upi_id": user.upi_id},
        "friends": [{"name": friend.name, "upi_id": friend.upi_id} for friend in accounts.friends(user.id)],
    }
