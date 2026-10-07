"""Phone QR pairing endpoints (backend side; frontend renders the QR later).

POST   /api/cameras/{camera_id}/pairing   -> {code, expires_at, status}
GET    /api/pairing/{code}/status         -> {status, camera_id, expires_at} (owner only)
POST   /api/pairing/{code}/revoke         -> {revoked: true} (owner only)

The phone itself never calls these; it presents the code at
/ws/cameras/{camera_id}?pairing=<code> (or POST /api/pairing/{code}/claim for
browser-based status checks, which validates without consuming).
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.cameras.pairing import (
    PairingError,
    PairingStatus,
    PairingStore,
    pairings,
)
from backend.app.core.config import settings
from backend.app.core.logging import log_event
from backend.app.core.security import CurrentUser, require_user
from backend.app.db.repositories import CameraRepository
from backend.app.db.session import get_db

router = APIRouter(tags=["pairing"])


def _store() -> PairingStore:
    # Rebind TTL from settings at call time so tests can shrink it.
    pairings._ttl = settings.pairing_ttl_seconds
    return pairings


@router.post("/api/cameras/{camera_id}/pairing")
def create_pairing(
    camera_id: str,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    camera = CameraRepository(db).get(user.id, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    if camera.source_type not in ("browser", "phone"):
        raise HTTPException(
            status_code=400, detail="Pairing is for browser/phone cameras only"
        )
    session = _store().create(user.id, camera_id)
    log_event("pairing_created", status="ok", user_id=user.id, camera_id=camera_id)
    return {
        "code": session.code,
        "camera_id": camera_id,
        "status": session.status.value,
        "expires_at": session.expires_at,
        "expires_in_seconds": int(session.expires_at - time.monotonic()),
    }


@router.get("/api/pairing/{code}/status")
def pairing_status(
    code: str, user: CurrentUser = Depends(require_user), db: Session = Depends(get_db)
):
    store = _store()
    try:
        store.status(
            code
        )  # validates existence + refreshes expiry; raises 404 if unknown
    except PairingError:
        raise HTTPException(status_code=404, detail="Unknown pairing code")
    session = store._sessions[code]
    if session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Unknown pairing code")
    if session.status == PairingStatus.PAIRED:
        log_event(
            "pairing_completed",
            status="ok",
            user_id=user.id,
            camera_id=session.camera_id,
        )
    return {
        "code": code,
        "camera_id": session.camera_id,
        "status": session.status.value,
        "expires_at": session.expires_at,
    }


@router.post("/api/pairing/{code}/revoke")
def revoke_pairing(
    code: str, user: CurrentUser = Depends(require_user), db: Session = Depends(get_db)
):
    if not _store().revoke(user.id, code):
        raise HTTPException(status_code=404, detail="Unknown pairing code")
    return {"revoked": True}
