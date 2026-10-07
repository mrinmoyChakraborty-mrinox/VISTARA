"""Camera REST endpoints. All queries are scoped to the authenticated user."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.logging import log_event
from backend.app.core.security import CurrentUser, require_user
from backend.app.db.repositories import CameraRepository, CameraSessionRepository
from backend.app.db.session import get_db

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


class CameraIn(BaseModel):
    name: str
    source_type: str = "browser"
    config: dict = {}


class CameraOut(BaseModel):
    id: uuid.UUID
    name: str
    source_type: str
    status: str
    config: dict
    created_at: datetime
    last_seen_at: datetime | None


def _to_out(camera) -> CameraOut:
    return CameraOut(
        id=camera.id,
        name=camera.name,
        source_type=camera.source_type,
        status=camera.status,
        config=camera.config or {},
        created_at=camera.created_at,
        last_seen_at=camera.last_seen_at,
    )


@router.get("", response_model=list[CameraOut])
def list_cameras(
    user: CurrentUser = Depends(require_user), db: Session = Depends(get_db)
):
    return [_to_out(c) for c in CameraRepository(db).list(user.id)]


@router.post("", response_model=CameraOut, status_code=201)
def create_camera(
    body: CameraIn,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    camera = CameraRepository(db).create(
        user.id, body.name, body.source_type, body.config
    )
    db.commit()
    log_event(
        "camera_connected", status="created", user_id=user.id, camera_id=str(camera.id)
    )
    return _to_out(camera)


@router.delete("/{camera_id}", status_code=204)
def delete_camera(
    camera_id: str,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    if not CameraRepository(db).delete(user.id, camera_id):
        raise HTTPException(status_code=404, detail="Camera not found")
    db.commit()
    return None


@router.post("/{camera_id}/start", response_model=CameraOut)
def start_camera(
    camera_id: str,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo = CameraRepository(db)
    camera = repo.get(user.id, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    repo.update_status(user.id, camera_id, "active")
    CameraSessionRepository(db).start(user.id, camera_id)
    db.commit()
    log_event(
        "camera_connected", status="started", user_id=user.id, camera_id=camera_id
    )
    return _to_out(camera)


@router.post("/{camera_id}/stop", response_model=CameraOut)
def stop_camera(
    camera_id: str,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo = CameraRepository(db)
    camera = repo.get(user.id, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    repo.update_status(user.id, camera_id, "idle")
    CameraSessionRepository(db).stop(user.id, camera_id)
    db.commit()
    log_event(
        "camera_disconnected", status="stopped", user_id=user.id, camera_id=camera_id
    )
    return _to_out(camera)


@router.get("/{camera_id}/state")
def camera_state(
    camera_id: str,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    camera = CameraRepository(db).get(user.id, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    session = CameraSessionRepository(db).latest(user.id, camera_id)
    return {
        "camera": _to_out(camera).model_dump(mode="json"),
        "session": {
            "id": str(session.id) if session else None,
            "status": session.status if session else None,
            "started_at": session.started_at.isoformat() if session else None,
            "ended_at": session.ended_at.isoformat()
            if session and session.ended_at
            else None,
        },
    }
