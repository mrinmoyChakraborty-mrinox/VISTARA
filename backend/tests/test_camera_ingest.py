"""WS ingestion hardening + pairing/gateway REST + MJPEG live fixture."""

from __future__ import annotations

import base64
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from backend.app.api.ingest import IngestSession, decode_frame_data
from backend.tests.conftest import auth, create_camera, frame_bytes


def test_decode_rejects_garbage_and_oversize():
    jpeg, err = decode_frame_data(None)
    assert jpeg is None and err
    jpeg, err = decode_frame_data("!!!not-base64!!!")
    assert jpeg is None and err
    big = "A" * (10 * 1024 * 1024)
    jpeg, err = decode_frame_data(big)
    assert jpeg is None and "exceeds" in err


def test_ingest_session_seq_tracking():
    from backend.app.core.config import settings

    settings.ingest_max_fps = 0.0  # unlimited for determinism
    s = IngestSession(camera_id="c", user_id="u")
    assert s.check_seq(None) is None
    assert s.check_seq("abc") is not None
    assert s.check_seq(1) is None
    assert "duplicate" in (s.check_seq(1) or "")
    assert s.check_seq(4) is None and s.seq_gaps == 2  # missed 2,3


def test_ws_malformed_and_oversize_frames(client):
    cam = create_camera(client, "WSH", user="user-a")
    with client.websocket_connect(f"/ws/cameras/{cam}?token=mock:user-a") as ws:
        assert ws.receive_json()["type"] == "connection_state"
        ws.send_json({"type": "frame", "data": "!!!not-base64!!!"})
        assert ws.receive_json()["type"] == "error"
        ws.send_json({"type": "frame"})  # missing data
        assert ws.receive_json()["type"] == "error"
        ws.send_json({"type": "frame", "data": base64.b64encode(b"tiny").decode()})
        assert ws.receive_json()["type"] == "error"
        ws.send_json("just a string")
        assert ws.receive_json()["type"] == "error"
        ws.send_json({"type": "stop"})


def test_ws_duplicate_seq_rejected(client):
    cam = create_camera(client, "WSS", user="user-a")
    with client.websocket_connect(f"/ws/cameras/{cam}?token=mock:user-a") as ws:
        assert ws.receive_json()["type"] == "connection_state"
        data = base64.b64encode(frame_bytes(0)).decode()
        ws.send_json({"type": "frame", "data": data, "seq": 1})
        # First frame finalizes the initial baseline -> processing messages.
        assert ws.receive_json() == {"type": "processing", "state": "analyzing"}
        assert ws.receive_json() == {"type": "processing", "state": "idle"}
        ws.send_json({"type": "frame", "data": data, "seq": 1})  # duplicate
        # The duplicate error is synchronous and guaranteed; the baseline
        # memory_created broadcast may arrive before or after it (worker timing).
        seen = set()
        for _ in range(4):
            msg_type = ws.receive_json()["type"]
            seen.add(msg_type)
            if msg_type == "error":
                break
        assert "error" in seen
        ws.send_json({"type": "stop"})
    # The baseline memory was persisted regardless of broadcast timing; the
    # mock-VLM worker may still be finishing, so poll briefly (bounded).
    import time as _time

    deadline = _time.monotonic() + 10.0
    mems = []
    while _time.monotonic() < deadline:
        mems = client.get("/api/memories", headers=auth("user-a")).json()
        if any(m.get("is_baseline") for m in mems):
            break
        _time.sleep(0.05)
    assert any(m.get("is_baseline") for m in mems)


def test_ws_pairing_auth_flow(client):
    cam = create_camera(client, "Phone", user="user-a")
    # Unknown code rejected.
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/cameras/{cam}?pairing=bogus"):
            pass
    # Real pairing code works once, then replay is rejected.
    res = client.post(f"/api/cameras/{cam}/pairing", headers=auth("user-a"))
    assert res.status_code == 200, res.text
    code = res.json()["code"]
    with client.websocket_connect(f"/ws/cameras/{cam}?pairing={code}") as ws:
        assert ws.receive_json()["type"] == "connection_state"
        ws.send_json({"type": "stop"})
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/cameras/{cam}?pairing={code}"):
            pass


def test_pairing_rest_lifecycle(client):
    cam = create_camera(client, "Pair", user="user-a")
    res = client.post(f"/api/cameras/{cam}/pairing", headers=auth("user-a"))
    assert res.status_code == 200
    code = res.json()["code"]
    assert (
        client.get(f"/api/pairing/{code}/status", headers=auth("user-a")).json()[
            "status"
        ]
        == "pending"
    )
    # Cross-user status hidden.
    assert (
        client.get(f"/api/pairing/{code}/status", headers=auth("user-b")).status_code
        == 404
    )
    assert (
        client.post(f"/api/pairing/{code}/revoke", headers=auth("user-b")).status_code
        == 404
    )
    assert client.post(
        f"/api/pairing/{code}/revoke", headers=auth("user-a")
    ).json() == {"revoked": True}
    # Pairing a network camera is rejected (browser/phone only).
    cam2 = client.post(
        "/api/cameras",
        json={
            "name": "rtsp",
            "source_type": "rtsp",
            "config": {"url": "rtsp://camera.example.com/live"},
        },
        headers=auth("user-a"),
    ).json()["id"]
    assert (
        client.post(f"/api/cameras/{cam2}/pairing", headers=auth("user-a")).status_code
        == 400
    )


def test_gateway_rest_and_ws(client):
    reg = client.post(
        "/api/gateways/register", json={"name": "shop"}, headers=auth("user-a")
    ).json()
    assert reg["token"].startswith("gw_")
    cam = create_camera(client, "GW cam", user="user-a")
    attach = client.post(
        f"/api/gateways/{reg['gateway_id']}/cameras",
        json={"external_id": "ch1", "camera_id": cam},
        headers=auth("user-a"),
    )
    assert attach.status_code == 200
    # Cross-user attach blocked.
    assert (
        client.post(
            f"/api/gateways/{reg['gateway_id']}/cameras",
            json={"external_id": "ch2", "camera_id": cam},
            headers=auth("user-b"),
        ).status_code
        == 404
    )
    with client.websocket_connect(
        f"/ws/gateways/{reg['gateway_id']}?token={reg['token']}"
    ) as ws:
        assert ws.receive_json()["type"] == "registered"
        ws.send_json({"type": "register_camera", "external_id": "ch1"})
        assert ws.receive_json()["type"] == "registered"
        ws.send_json(
            {
                "type": "frame",
                "external_id": "ch1",
                "data": base64.b64encode(frame_bytes(0)).decode(),
            }
        )
        ws.send_json({"type": "frame", "external_id": "unknown"})
        assert ws.receive_json()["type"] == "error"
    # Bad token rejected.
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/gateways/{reg['gateway_id']}?token=bogus"):
            pass
    assert client.post(
        f"/api/gateways/{reg['gateway_id']}/revoke", headers=auth("user-a")
    ).json() == {"revoked": True}


# ------------------------------------------------- MJPEG live local fixture
def _jpeg_bytes() -> bytes:
    import cv2
    import numpy as np

    img = np.full((48, 64, 3), 90, np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return bytes(buf)


class _MjpegHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/bad":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html>not mjpeg</html>")
            return
        jpeg = _jpeg_bytes()
        body = (
            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            b"--frame\r\nContent-Type: image/jpeg\r\n\r\nGARBAGE\r\n"
            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        )
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass


def test_mjpeg_source_against_local_fixture():
    server = HTTPServer(("127.0.0.1", 0), _MjpegHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        from backend.app.cameras.factory import create_source

        src = create_source(
            "c", "u", "n", "mjpeg", {"url": f"http://127.0.0.1:{port}/stream"}
        )
        src._allow_private = True
        src.connect()
        frame = src.read_frame()  # first good part (skips nothing yet)
        assert frame is not None and (frame.width, frame.height) == (64, 48)
        frame2 = src.read_frame()  # skips the garbage part, returns next good one
        assert frame2 is not None
        src.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_mjpeg_bad_content_type_fails_cleanly():
    server = HTTPServer(("127.0.0.1", 0), _MjpegHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        from backend.app.cameras.factory import create_source
        from backend.app.cameras.ffmpeg_reader import TransportError

        src = create_source(
            "c", "u", "n", "mjpeg", {"url": f"http://127.0.0.1:{port}/bad"}
        )
        src._allow_private = True
        try:
            with __import__("pytest").raises(TransportError):
                src.connect()
        finally:
            src.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
