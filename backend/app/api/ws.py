"""WebSocket contract for browser cameras.

  /ws/cameras/{camera_id}?token=<jwt>

CLIENT -> SERVER: {"type":"camera_connected"} | {"type":"frame","data":"<b64 jpeg>","ts":<ms>} | {"type":"stop"}
SERVER -> CLIENT: connection_state | processing | change_detected | memory_created | error

Frames are NOT streamed back to the client (it keeps its own local preview).
"""

from __future__ import annotations

import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.api.deps import get_vision_provider
from backend.app.cameras.manager import manager
from backend.app.core.config import settings
from backend.app.core.logging import log_event
from backend.app.core.security import AuthError, user_from_ws_token
from backend.app.db.repositories import CameraRepository
from backend.app.db.session import session_scope
from backend.app.perception.gate import GateConfig
from backend.app.perception.pipeline import build_event_payload, frame_to_bgr
from backend.app.workers.camera_worker import CameraWorker

router = APIRouter()


async def _send(ws: WebSocket, **payload) -> None:
    await ws.send_json(payload)


@router.websocket("/ws/cameras/{camera_id}")
async def camera_ws(websocket: WebSocket, camera_id: str):
    token = websocket.query_params.get("token")
    try:
        user = user_from_ws_token(token)
    except AuthError as exc:
        await websocket.close(code=4401, reason=exc.detail)
        return

    # Ownership check against authoritative DB record.
    try:
        with session_scope() as db:
            camera = CameraRepository(db).get(user.id, camera_id)
    except Exception:
        camera = None
    if camera is None:
        await websocket.close(code=4404, reason="Camera not found")
        return

    await websocket.accept()
    await _send(websocket, type="connection_state", state="connected")

    runtime = manager.get(camera_id)
    if runtime is None:
        runtime = await manager.add(
            camera_id=camera_id,
            user_id=user.id,
            name=camera.name,
            source_type=camera.source_type,
            config=camera.config or {},
            gate_config=GateConfig(
                change_threshold=settings.change_threshold,
                cooldown_seconds=settings.cooldown_seconds,
                persistence_frames=settings.persistence_frames,
                use_ssim=settings.use_ssim,
            ),
        )

    vision = get_vision_provider()

    async def on_result(result, memory_id, events):
        await _send(
            websocket,
            type="memory_created",
            memory_id=memory_id,
            summary=result.perception.scene.summary,
            events=events,
        )

    worker = CameraWorker(runtime, vision, on_result)
    worker.start()
    runtime.source.mark_connected()

    try:
        while True:
            message = await websocket.receive_json()
            mtype = message.get("type")

            if mtype == "camera_connected":
                runtime.source.mark_connected()
                await _send(websocket, type="connection_state", state="connected")

            elif mtype == "frame":
                data = message.get("data")
                if not data:
                    continue
                import base64

                try:
                    jpeg = base64.b64decode(data)
                    bgr = frame_to_bgr(jpeg)
                except Exception as exc:  # noqa: BLE001
                    await _send(websocket, type="error", message=f"bad frame: {exc}")
                    continue

                now = time.monotonic()
                runtime.source.note_frame()
                runtime.buffer.push(bgr, now)
                decision = runtime.gate.update(bgr, now)
                if decision.fired:
                    log_event(
                        "change_detected",
                        status="ok",
                        user_id=user.id,
                        camera_id=camera_id,
                        extra={"score": round(decision.score, 4)},
                    )
                    await _send(
                        websocket,
                        type="change_detected",
                        score=round(decision.score, 4),
                    )
                    await _send(websocket, type="processing", state="analyzing")
                    ctx = build_event_payload(runtime.buffer)
                    if ctx is not None:
                        ctx.camera_id = camera_id
                        ctx.user_id = user.id
                        ctx.score = decision.score
                        await runtime.event_queue.put(ctx)
                    await _send(websocket, type="processing", state="idle")

            elif mtype == "stop":
                break
            else:
                await _send(
                    websocket, type="error", message=f"unknown message type: {mtype}"
                )

    except WebSocketDisconnect:
        pass
    finally:
        await worker.stop()
        runtime.source.mark_disconnected()
        log_event(
            "camera_disconnected", status="closed", user_id=user.id, camera_id=camera_id
        )
