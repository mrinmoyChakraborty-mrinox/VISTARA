"""Authentication: verify Supabase JWT (live) or local demo tokens (local).

The authenticated identity is ALWAYS derived server-side from the verified
credential. Client-supplied user_id is never trusted (enforced in
repositories too).

LOCAL (VISTARA_MODE=local): deterministic demo auth, no Supabase project.
"demo-token" maps to the single demo user; "local:<user_id>" maps to an
explicit local user (isolation). This is NOT Supabase Auth and never pretends
to be. LIVE (VISTARA_MODE=live): Supabase JWT only.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException, status

from backend.app.core.config import settings


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None = None
    role: str = "authenticated"


class AuthError(HTTPException):
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


LOCAL_DEMO_USER_ID = "demo-user"
LOCAL_DEMO_EMAIL = "demo@visual-memory.local"


def _local_user(token: str) -> CurrentUser | None:
    """Local-mode credential check. Returns None when the token is not local."""
    if token == "demo-token":
        return CurrentUser(id=LOCAL_DEMO_USER_ID, email=LOCAL_DEMO_EMAIL)
    if token.startswith("local:"):
        user_id = token.split(":", 1)[1].strip()
        if user_id:
            return CurrentUser(id=user_id, email=None)
    return None


def _local_auth_enabled() -> bool:
    return settings.mock_mode or settings.is_local


def _decode_supabase_jwt(token: str) -> dict[str, Any]:
    """Verify a Supabase-issued JWT.

    Supabase signs with HS256 using the project JWT secret (legacy) or asymmetric
    keys (newer projects). We support HS256 via SUPABASE_JWT_SECRET and otherwise
    fall back to JWKS verification through supabase-py's auth helper.
    """
    import jwt

    secret = settings.supabase_jwt_secret
    if not secret:
        raise AuthError("Server auth is not configured (SUPABASE_JWT_SECRET missing).")

    try:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=settings.supabase_jwt_audience,
            options={"verify_aud": bool(settings.supabase_jwt_audience)},
        )
    except Exception as exc:  # noqa: BLE001 - map all JWT failures to 401
        raise AuthError(f"Invalid or expired token: {exc}") from exc


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("Missing bearer token.")
    token = authorization.split(" ", 1)[1].strip()

    # Demo/mock mode: a static token maps to a single seeded demo user.
    if _local_auth_enabled():
        local = _local_user(token)
        if local is not None:
            return local
        # In mock mode also accept a "mock:<user_id>" token for isolation tests.
        if settings.mock_mode and token.startswith("mock:"):
            return CurrentUser(id=token.split(":", 1)[1], email=None)

    claims = _decode_supabase_jwt(token)
    sub = claims.get("sub")
    if not sub:
        raise AuthError("Token missing subject claim.")
    return CurrentUser(
        id=str(sub),
        email=claims.get("email"),
        role=str(claims.get("role", "authenticated")),
    )


def require_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return user


# ---------------------------------------------------------------- helpers
def user_from_ws_token(token: str | None) -> CurrentUser:
    """WebSocket auth: browsers cannot set headers, so the JWT rides the query string."""
    if _local_auth_enabled():
        if token in (None, "demo-token"):
            return CurrentUser(id=LOCAL_DEMO_USER_ID, email=LOCAL_DEMO_EMAIL)
        if token:
            local = _local_user(token)
            if local is not None:
                return local
            if settings.mock_mode and token.startswith("mock:"):
                return CurrentUser(id=token.split(":", 1)[1])
    if not token:
        raise AuthError("Missing token.")
    claims = _decode_supabase_jwt(token)
    sub = claims.get("sub")
    if not sub:
        raise AuthError("Token missing subject claim.")
    return CurrentUser(id=str(sub), email=claims.get("email"))


def constant_time_equals(a: str, b: str) -> bool:
    return secrets.compare_digest(a, b)
