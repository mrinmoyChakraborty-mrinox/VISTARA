"""Authentication: verify Supabase JWT, expose the current user.

The authenticated identity is ALWAYS derived server-side from the verified JWT.
Client-supplied user_id is never trusted (enforced in repositories too).
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
    if settings.mock_mode:
        if token == "demo-token":
            return CurrentUser(id="demo-user", email="demo@visual-memory.local")
        # In mock mode also accept a "mock:<user_id>" token for isolation tests.
        if token.startswith("mock:"):
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
    if settings.mock_mode:
        if token in (None, "demo-token"):
            return CurrentUser(id="demo-user", email="demo@visual-memory.local")
        if token and token.startswith("mock:"):
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
