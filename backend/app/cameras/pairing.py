"""Phone QR pairing (backend side). Phone stays browser-based; no native code.

Flow: desktop creates pairing session -> backend issues short-lived single-use
code -> desktop renders QR (frontend) -> phone opens URL with code -> backend
validates -> phone WS frames attach to that camera.

Security: codes are short-lived, single-use, user+camera scoped, replay-safe
(consumed codes are rejected), revocable/expirable. No permanent secret in QR.
Store is in-memory (single process); a multi-process deployment must move this
to the database — documented, not built (no new infra this phase).
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from enum import Enum


class PairingStatus(str, Enum):
    PENDING = "pending"
    PAIRED = "paired"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class PairingSession:
    code: str
    user_id: str
    camera_id: str
    created_at: float
    expires_at: float
    status: PairingStatus = PairingStatus.PENDING
    consumed_at: float | None = None
    uses: int = 0


class PairingError(ValueError):
    pass


class PairingStore:
    """In-memory pairing sessions with TTL + single-use semantics."""

    def __init__(self, ttl_seconds: float = 600.0, time_fn=None):
        self._ttl = ttl_seconds
        self._now = time_fn or time.monotonic
        self._sessions: dict[str, PairingSession] = {}

    # ------------------------------------------------------------- lifecycle
    def create(self, user_id: str, camera_id: str) -> PairingSession:
        self._reap()
        code = secrets.token_urlsafe(24)
        now = self._now()
        session = PairingSession(
            code=code,
            user_id=user_id,
            camera_id=camera_id,
            created_at=now,
            expires_at=now + self._ttl,
        )
        self._sessions[code] = session
        return session

    def status(self, code: str) -> PairingStatus:
        session = self._sessions.get(code)
        if session is None:
            raise PairingError("unknown pairing code")
        self._refresh(session)
        return session.status

    def claim(self, code: str, user_id: str) -> PairingSession:
        """Phone presents the code. Single-use: first valid claim wins, replays rejected."""
        session = self._sessions.get(code)
        if session is None:
            raise PairingError("unknown pairing code")
        self._refresh(session)
        if session.status != PairingStatus.PENDING:
            raise PairingError(f"pairing is {session.status.value}, not usable")
        # The code is bound to the desktop user's camera; a different claimant is rejected.
        if session.user_id != user_id:
            raise PairingError("pairing code does not belong to this user")
        session.uses += 1
        session.consumed_at = self._now()
        session.status = PairingStatus.PAIRED
        return session

    def mark_active(self, code: str) -> None:
        session = self._sessions.get(code)
        if session is not None and session.status == PairingStatus.PAIRED:
            session.status = PairingStatus.ACTIVE

    def revoke(self, user_id: str, code: str) -> bool:
        session = self._sessions.get(code)
        if session is None or session.user_id != user_id:
            return False
        session.status = PairingStatus.REVOKED
        return True

    def session_for_camera(self, camera_id: str) -> PairingSession | None:
        for session in self._sessions.values():
            self._refresh(session)
            if session.camera_id == camera_id and session.status in (
                PairingStatus.PAIRED,
                PairingStatus.ACTIVE,
            ):
                return session
        return None

    # --------------------------------------------------------------- helpers
    def _refresh(self, session: PairingSession) -> None:
        if (
            session.status == PairingStatus.PENDING
            and self._now() >= session.expires_at
        ):
            session.status = PairingStatus.EXPIRED

    def _reap(self) -> None:
        now = self._now()
        stale = [
            code
            for code, s in self._sessions.items()
            if s.status in (PairingStatus.EXPIRED, PairingStatus.REVOKED)
            and now - s.expires_at > 3600
        ]
        for code in stale:
            del self._sessions[code]


pairings = PairingStore()
