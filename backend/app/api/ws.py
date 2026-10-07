"""WebSocket contract for browser/phone cameras (contract unchanged).

  /ws/cameras/{camera_id}?token=<jwt>          (desktop browser, Supabase JWT)
  /ws/cameras/{camera_id}?pairing=<code>       (phone browser, QR pairing code)

CLIENT -> SERVER: {"type":"camera_connected"} | {"type":"frame","data":"<b64 jpeg>","ts":<ms>,"seq":<n>} | {"type":"stop"}
SERVER -> CLIENT: connection_state | processing | change_detected | memory_created | error

`seq` is optional and advisory; duplicates are ignored, gaps are counted.
Frames are NOT streamed back (the client keeps its own preview).
"""

from __future__ import annotations

import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.api.deps import get_vision_provider
from backend.app.api.ingest import IngestSession, decode_frame_data, ingest_jpeg
from backend.app.cameras.manager import manager
from backend.app.cameras.pairing import PairingError, pairings
from backend.app.core.config import settings
from backend.app.core.logging import log_event
from backend.app.core.security import AuthError, user_from_ws_token
from backend.app.db.repositories import CameraRepository
from backend.app.db.session import session_scope
from backend.app.perception.baseline import (
    BaselineStatus,
    adopt_prior_state,
    post_ingest,
)
from backend.app.perception.gate import GateConfig

router = APIRouter()


async def _send(ws: WebSocket, **payload) -> None:
    await ws.send_json(payload)


def _authenticate(token: str | None, pairing_code: str | None, camera_id: str):
    """JWT path or single-use phone-pairing path. Returns (user, via_pairing)."""
    if pairing_code:
        # Phone path: claim the single-use code. The user/camera binding comes
        # from the server-side pairing record, never from client input.
        record = pairings._sessions.get(pairing_code)
        if record is None:
            raise AuthError("Unknown pairing code.")
        try:
            claimed = pairings.claim(pairing_code, record.user_id)
        except PairingError as exc:
            raise AuthError(str(exc)) from exc
        if claimed.camera_id != camera_id:
            raise AuthError("Pairing code is for a different camera.")
        from backend.app.core.security import CurrentUser

        pairings.mark_active(pairing_code)
        return CurrentUser(id=claimed.user_id), True
    if not token:
        raise AuthError("Missing token.")
    return user_from_ws_token(token), False


@router.websocket("/ws/cameras/{camera_id}")
async def camera_ws(websocket: WebSocket, camera_id: str):
    token = websocket.query_params.get("token")
    pairing_code = websocket.query_params.get("pairing")
    try:
        user, via_pairing = _authenticate(token, pairing_code, camera_id)
    except AuthError as exc:
        await websocket.close(code=4401, reason=exc.detail)
        return

    # Ownership check against the authoritative DB record.
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
    fresh = runtime is None
    if fresh:
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
            await websocket.close(code=4400, reason=str(exc)[:120])
            return

    # A second connection to the same camera reuses the runtime (never duplicates work).
    if runtime.source.metadata.user_id != user.id:
        await websocket.close(code=4403, reason="Camera owned by another user")
        return

    if fresh:
        # Reconnects/restarts adopt persisted memories as the baseline instead of
        # creating a second "initial scene". Only a camera with no history baselines.
        adopt_prior_state(runtime, user.id, camera_id)

    manager.ensure_worker(runtime, get_vision_provider())
    listener = manager.add_listener(runtime)
    session = IngestSession(camera_id=camera_id, user_id=user.id)
    runtime.source.mark_connected()
    log_event(
        "camera_connected",
        status="ok",
        user_id=user.id,
        camera_id=camera_id,
        extra={"via": "pairing" if via_pairing else "token"},
    )

    sender_done = False

    async def _forward_results():
        nonlocal sender_done
        import asyncio

        while not sender_done:
            try:
                payload = await listener.get()
            except asyncio.CancelledError:
                break
            try:
                await _send(websocket, **payload)
            except Exception:  # noqa: BLE001 - socket gone; loop below exits
                break
            finally:
                listener.task_done()

    import asyncio

    sender = asyncio.create_task(_forward_results())
    try:
        while True:
            try:
                message = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except Exception:  # noqa: BLE001 - malformed JSON frame
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

            if mtype == "camera_connected":
                runtime.source.mark_connected()
                await _send(websocket, type="connection_state", state="connected")

            elif mtype == "frame":
                now = time.monotonic()
                if not session.check_sample_gate(now):
                    continue  # ingest FPS guard: drop silently, counted
                seq_err = session.check_seq(message.get("seq"))
                if seq_err and "duplicate" in seq_err:
                    await _send(websocket, type="error", message=seq_err)
                    continue
                if seq_err:
                    await _send(websocket, type="error", message=seq_err)
                    continue
                jpeg, err = decode_frame_data(message.get("data"))
                if err is not None:
                    session.dropped_invalid += 1
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
                action = post_ingest(runtime, user.id, now, result["score"])
                baseline_ctx = action["baseline_ctx"]
                if baseline_ctx is not None:
                    # Initial visual baseline: inventory state first, no change
                    # events yet. The worker persists it and marks the camera ready.
                    manager.offer_event(runtime, baseline_ctx)
                    await _send(websocket, type="processing", state="analyzing")
                    await _send(websocket, type="processing", state="idle")
                    continue
                if action["emit_change"] and result["fired"]:
                    await _send(
                        websocket, type="change_detected", score=result["score"]
                    )
                    await _send(websocket, type="processing", state="analyzing")
                    # processing/idle closes when the worker broadcasts memory_created;
                    # send idle here to preserve the existing contract ordering.
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
        sender_done = True
        sender.cancel()
        try:
            await sender
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001
            pass
        manager.remove_listener(runtime, listener)
        # Last connection out stops the source; runtime stays for reconnects.
        if not runtime.listeners:
            runtime.source.mark_disconnected()
        log_event(
            "camera_disconnected", status="closed", user_id=user.id, camera_id=camera_id
        )
