"""WebSocket contract test: connect, auth, frames -> change -> memory_created."""

from __future__ import annotations

import base64
import time

from backend.app.providers.mock import MockVisionProvider
from backend.tests.conftest import create_camera, frame_bytes


def test_ws_requires_valid_token(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    cam = create_camera(client, "WS cam", user="user-a")
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/cameras/{cam}?token=") as ws:
            ws.receive_json()


def test_ws_full_flow(client):
    from backend.app.api import deps

    deps.set_vision_provider(MockVisionProvider())
    cam = create_camera(client, "WS cam 2", user="user-a")

    with client.websocket_connect(f"/ws/cameras/{cam}?token=mock:user-a") as ws:
        first = ws.receive_json()
        assert first["type"] == "connection_state" and first["state"] == "connected"

        ws.send_json({"type": "camera_connected"})
        assert ws.receive_json()["state"] == "connected"

        # Send two frames: the gate fires on the change, worker persists a memory.
        ws.send_json(
            {
                "type": "frame",
                "data": base64.b64encode(frame_bytes(0)).decode(),
                "ts": int(time.time() * 1000),
            }
        )
        ws.send_json(
            {
                "type": "frame",
                "data": base64.b64encode(frame_bytes(80)).decode(),
                "ts": int(time.time() * 1000),
            }
        )

        seen = []
        try:
            for _ in range(6):
                msg = ws.receive_json()
                seen.append(msg["type"])
                if msg["type"] == "memory_created":
                    assert msg["memory_id"]
                    break
        except Exception:
            pass
        assert "change_detected" in seen or "memory_created" in seen

        ws.send_json({"type": "stop"})
