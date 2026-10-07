"""Local gateway protocol: registration REST + outbound WSS.

REST (user JWT):
  POST /api/gateways/register {name}            -> {gateway_id, token} (token shown once)
  POST /api/gateways/{gateway_id}/revoke        -> {revoked: true}
  POST /api/gateways/{gateway_id}/cameras       -> attach external camera to a logical camera

WS (gateway token, OUTBOUND from the LAN gateway):
  /ws/gateways/{gateway_id}?token=<gateway_token>
  gateway -> server: register_camera | frame | health
  server  -> gateway: registered | error
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.deps import get_vision_provider
from backend.app.api.ingest import IngestSession, decode_frame_data, ingest_jpeg
from backend.app.cameras.gateway import GatewayError, gateways
from backend.app.cameras.manager import manager
from backend.app.cameras.security import sanitize_config_for_api
from backend.app.core.config import settings
from backend.app.core.logging import log_event
from backend.app.core.security import CurrentUser, require_user
from backend.app.db.repositories import CameraRepository
from backend.app.db.session import get_db, session_scope
from backend.app.perception.baseline import (
    BaselineStatus,
    adopt_prior_state,
    post_ingest,
)
from backend.app.perception.gate import GateConfig

router = APIRouter(tags=["gateway"])


class GatewayRegisterIn(BaseModel):
    name: str


class GatewayCameraAttachIn(BaseModel):
    external_id: str
    camera_id: str


@router.post("/api/gateways/register")
def register_gateway(
    body: GatewayRegisterIn,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    reg = gateways.register(user.id, body.name)
    log_event("gateway_connected", status="registered", user_id=user.id)
    return {"gateway_id": reg.gateway_id, "token": reg.token, "name": reg.name}


@router.post("/api/gateways/{gateway_id}/revoke")
def revoke_gateway(
    gateway_id: str,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    if not gateways.revoke(user.id, gateway_id):
        raise HTTPException(status_code=404, detail="Unknown gateway")
    return {"revoked": True}


@router.post("/api/gateways/{gateway_id}/cameras")
def attach_gateway_camera(
    gateway_id: str,
    body: GatewayCameraAttachIn,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    camera = CameraRepository(db).get(user.id, body.camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    try:
        gateways.attach_camera(gateway_id, body.external_id, body.camera_id, user.id)
    except GatewayError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "gateway_id": gateway_id,
        "external_id": body.external_id,
        "camera_id": body.camera_id,
    }


async def _send(ws: WebSocket, **payload) -> None:
    await ws.send_json(payload)


@router.websocket("/ws/gateways/{gateway_id}")
async def gateway_ws(websocket: WebSocket, gateway_id: str):
    token = websocket.query_params.get("token")
    try:
        reg = gateways.authenticate(token or "")
    except GatewayError:
        await websocket.close(code=4401, reason="Unknown gateway token")
        return
    if reg.gateway_id != gateway_id or not token:
        await websocket.close(code=4401, reason="Gateway mismatch")
        return

    await websocket.accept()
    gateways.mark_connected(gateway_id)
    log_event("gateway_connected", status="ok", user_id=reg.user_id)
    await _send(websocket, type="registered", gateway_id=gateway_id)

    sessions: dict[str, IngestSession] = {}
    try:
        while True:
            try:
                message = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except Exception:  # noqa: BLE001
                # Client is gone if we cannot even report the error; stop quietly
                # instead of raising into the ASGI server.
                try:
                    await _send(
                        websocket,
                        type="error",
                        message="unparseable message (expected JSON)",
                    )
                except Exception:  # noqa: BLE001
                    break
                continue
            if not isinstance(message, dict):
                await _send(
                    websocket, type="error", message="message must be a JSON object"
                )
                continue
            mtype = message.get("type")

            if mtype == "register_camera":
                external_id = message.get("external_id")
                camera_id = gateways.resolve_camera(gateway_id, external_id)
                if camera_id is None:
                    await _send(
                        websocket, type="error", message="external camera not attached"
                    )
                    continue
                await _send(
                    websocket,
                    type="registered",
                    external_id=external_id,
                    camera_id=camera_id,
                )

            elif mtype == "frame":
                external_id = message.get("external_id")
                if not isinstance(external_id, str) or not external_id:
                    await _send(websocket, type="error", message="external_id required")
                    continue
                camera_id = gateways.resolve_camera(gateway_id, external_id)
                if camera_id is None:
                    await _send(
                        websocket, type="error", message="external camera not attached"
                    )
                    continue
                try:
                    with session_scope() as db:
                        camera = CameraRepository(db).get(reg.user_id, camera_id)
                except Exception:
                    camera = None
                if camera is None:
                    await _send(websocket, type="error", message="camera not found")
                    continue
                runtime = manager.get(camera_id)
                fresh = runtime is None
                if fresh:
                    try:
                        runtime = await manager.add(
                            camera_id=camera_id,
                            user_id=reg.user_id,
                            name=camera.name,
                            source_type=camera.source_type,
                            config=sanitize_config_for_api(camera.config or {}),
                            event_queue_maxsize=settings.event_queue_maxsize,
                            gate_config=GateConfig(
                                change_threshold=settings.change_threshold,
                                cooldown_seconds=settings.cooldown_seconds,
                                persistence_frames=settings.persistence_frames,
                                use_ssim=settings.use_ssim,
                            ),
                        )
                    except ValueError as exc:
                        await _send(websocket, type="error", message=str(exc)[:200])
                        continue
                if fresh:
                    adopt_prior_state(runtime, reg.user_id, camera_id)
                manager.ensure_worker(runtime, get_vision_provider())
                listener = manager.add_listener(runtime)
                session = sessions.setdefault(
                    external_id, IngestSession(camera_id=camera_id, user_id=reg.user_id)
                )
                now = time.monotonic()
                if not session.check_sample_gate(now):
                    manager.remove_listener(runtime, listener)
                    continue
                jpeg, err = decode_frame_data(message.get("data"))
                manager.remove_listener(runtime, listener)
                if err is not None:
                    await _send(websocket, type="error", message=err)
                    continue
                assert jpeg is not None
                baseline_ready = runtime.baseline.status is BaselineStatus.READY
                result = ingest_jpeg(
                    runtime, session, jpeg, now=now, offer=baseline_ready
                )
                if not result["ok"]:
                    await _send(websocket, type="error", message=result["error"])
                    continue
                action = post_ingest(runtime, reg.user_id, now, result["score"])
                if action["baseline_ctx"] is not None:
                    manager.offer_event(runtime, action["baseline_ctx"])
                    continue
                if not action["emit_change"]:
                    continue

            elif mtype == "health":
                gateways.mark_connected(gateway_id)
                await _send(websocket, type="registered", gateway_id=gateway_id)

            else:
                await _send(
                    websocket, type="error", message=f"unknown message type: {mtype}"
                )

    except WebSocketDisconnect:
        pass
    finally:
        gateways.mark_disconnected(gateway_id)
        log_event("gateway_disconnected", status="closed", user_id=reg.user_id)
