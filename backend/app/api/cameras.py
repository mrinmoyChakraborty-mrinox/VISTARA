"""Camera REST endpoints. All queries are scoped to the authenticated user."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.cameras.manager import manager
from backend.app.cameras.nvr import NvrChannel, NvrSpec, expand_nvr_channels
from backend.app.cameras.security import (
    StreamURLRejected,
    sanitize_config_for_api,
    scrub_exceptions,
    validate_stream_url,
)
from backend.app.core.config import settings
from backend.app.core.logging import log_event
from backend.app.core.security import CurrentUser, require_user
from backend.app.db.repositories import CameraRepository, CameraSessionRepository
from backend.app.db.session import get_db
from backend.app.perception.gate import GateConfig

router = APIRouter(prefix="/api/cameras", tags=["cameras"])

PULL_SOURCE_TYPES = {"rtsp", "rtsps", "hls", "mjpeg", "video_file"}


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
        # Credential-bearing URLs never leave the server in raw form.
        config=sanitize_config_for_api(camera.config or {}),
        created_at=camera.created_at,
        last_seen_at=camera.last_seen_at,
    )


def _validate_camera_url(source_type: str, config: dict) -> None:
    """Eager SSRF-policy check for network cameras (also enforced at connect)."""
    stype = (source_type or "").lower()
    if stype not in PULL_SOURCE_TYPES or stype == "video_file":
        return
    url = (config or {}).get("url") or ""
    try:
        validate_stream_url(
            url, allow_private_networks=settings.cameras_allow_private_networks
        )
    except StreamURLRejected as exc:
        raise HTTPException(status_code=422, detail=f"stream URL rejected: {exc}")


def _validate_video_config(source_type: str, config: dict) -> None:
    """Eager check for recorded-video cameras: the file must open in cv2."""
    if (source_type or "").lower() != "video_file":
        return
    from backend.app.cameras.video import resolve_video_path, video_metadata

    try:
        path = resolve_video_path((config or {}).get("path"))
        video_metadata(path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"demo video rejected: {exc}")


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
    _validate_camera_url(body.source_type, body.config)
    _validate_video_config(body.source_type, body.config)
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
async def start_camera(
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

    # Pull sources (RTSP/HLS/MJPEG) start ingesting immediately on this loop.
    if (camera.source_type or "").lower() in PULL_SOURCE_TYPES:
        runtime = manager.get(camera_id)
        if runtime is None:
            try:
                runtime = await manager.add(
                    camera_id=camera_id,
                    user_id=user.id,
                    name=camera.name,
                    source_type=camera.source_type,
                    config=camera.config or {},
                    event_queue_maxsize=settings.event_queue_maxsize,
                    gate_config=GateConfig(
                        change_threshold=settings.change_threshold,
                        cooldown_seconds=settings.cooldown_seconds,
                        persistence_frames=settings.persistence_frames,
                        use_ssim=settings.use_ssim,
                    ),
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
        try:
            await manager.start_source(runtime)
        except Exception as exc:  # noqa: BLE001 - redacted, FAILED health instead
            log_event(
                "camera_reconnect_failed",
                status="error",
                user_id=user.id,
                camera_id=camera_id,
                message=scrub_exceptions(str(exc))[:200],
            )
            raise HTTPException(
                status_code=502,
                detail=f"source failed: {scrub_exceptions(str(exc))[:200]}",
            )
    return _to_out(camera)


@router.post("/{camera_id}/stop", response_model=CameraOut)
async def stop_camera(
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
    runtime = manager.require_owned(camera_id, user.id)
    if runtime is not None:
        await manager.stop_source(runtime)
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
        # Additive runtime health (None when the source is not running here).
        "runtime": manager.health(camera_id),
    }


@router.post("/{camera_id}/reset-baseline")
def reset_baseline(
    camera_id: str,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Clear the CURRENT runtime baseline state for repeatable demos.

    Historical memories are kept. The next ingested frames establish a fresh
    baseline instead of deriving deltas against the old one.
    """
    from backend.app.perception.baseline import BaselineStatus, BaselineTracker

    camera = CameraRepository(db).get(user.id, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    runtime = manager.get(camera_id)
    if runtime is None or runtime.source.metadata.user_id != user.id:
        raise HTTPException(status_code=404, detail="Camera is not running here")
    runtime.baseline = BaselineTracker()
    log_event("baseline_reset", status="ok", user_id=user.id, camera_id=camera_id)
    return {
        "camera_id": camera_id,
        "baseline": BaselineStatus.PENDING.value,
        "memories_kept": True,
    }


class NvrChannelIn(BaseModel):
    channel: int
    name: str = ""
    url: str = ""


class NvrExpandIn(BaseModel):
    name: str
    host: str
    username: str = ""
    password: str = ""
    channels: list[NvrChannelIn]
    url_template: str = "rtsp://{user}:{password}@{host}:554/Streaming/Channels/{ch}01"


@router.post("/nvr-expand", response_model=list[CameraOut], status_code=201)
def nvr_expand(
    body: NvrExpandIn,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Expand an NVR into individual logical RTSP cameras (one per channel)."""
    spec = NvrSpec(
        name=body.name,
        host=body.host,
        username=body.username,
        password=body.password,
        channels=[NvrChannel(c.channel, c.name, c.url) for c in body.channels],
        url_template=body.url_template,
    )
    definitions = expand_nvr_channels(spec, user.id)
    created = []
    repo = CameraRepository(db)
    for definition in definitions:
        _validate_camera_url("rtsp", definition["config"])
        created.append(
            repo.create(user.id, definition["name"], "rtsp", definition["config"])
        )
    db.commit()
    log_event(
        "camera_connected",
        status="nvr-expanded",
        user_id=user.id,
        extra={"nvr": body.name, "channels": len(created)},
    )
    return [_to_out(c) for c in created]
