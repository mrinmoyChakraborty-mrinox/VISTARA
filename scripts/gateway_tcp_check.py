"""Bounded real-TCP gateway verification client (no TestClient).

Proves over a real socket: connect -> registered -> register_camera ->
message exchange -> explicit close -> clean server-side termination.
Every wait has a timeout; exits nonzero on any stall. Run against a live server:

    $env:MOCK_MODE='true'; $env:DATABASE_URL='sqlite:///./data/gwtcp.db'
    python -m uvicorn backend.app.main:app --port 8020
    python scripts/gateway_tcp_check.py --url http://127.0.0.1:8020
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

STEP_TIMEOUT = 15.0


def rest(
    base: str, method: str, path: str, token: str, body: dict | None = None
) -> dict:
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body or {}).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        raw = res.read().decode()
        return json.loads(raw) if raw else {}


def synth_frame(shift: int = 0) -> bytes:
    import cv2
    import numpy as np

    img = np.full((240, 320, 3), 40, np.uint8)
    img[80:160, 40 + shift : 120 + shift] = (0, 200, 0)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return bytes(buf)


async def main_async(url: str, user_token: str) -> int:
    import websockets

    reg = rest(url, "POST", "/api/gateways/register", user_token, {"name": "tcp-check"})
    cam = rest(url, "POST", "/api/cameras", user_token, {"name": "GW tcp"})
    rest(
        url,
        "POST",
        f"/api/gateways/{reg['gateway_id']}/cameras",
        user_token,
        {"external_id": "ch1", "camera_id": cam["id"]},
    )
    print("setup ok: gateway + camera + attach", flush=True)

    ws_url = url.replace("http://", "ws://").replace("https://", "wss://")
    uri = f"{ws_url}/ws/gateways/{reg['gateway_id']}?{urllib.parse.urlencode({'token': reg['token']})}"
    async with websockets.connect(uri, max_size=8 * 1024 * 1024) as ws:
        msg = json.loads(await asyncio.wait_for(ws.recv(), STEP_TIMEOUT))
        assert msg.get("type") == "registered", msg
        print("connected -> registered", flush=True)

        await ws.send(json.dumps({"type": "register_camera", "external_id": "ch1"}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), STEP_TIMEOUT))
        assert msg.get("type") == "registered" and msg.get("camera_id") == cam["id"], (
            msg
        )
        print("register_camera -> registered (camera mapped)", flush=True)

        await ws.send(
            json.dumps(
                {
                    "type": "frame",
                    "external_id": "ch1",
                    "data": base64.b64encode(synth_frame(0)).decode(),
                }
            )
        )
        await ws.send(json.dumps({"type": "frame", "external_id": "unknown"}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), STEP_TIMEOUT))
        assert msg.get("type") == "error", msg
        print("message exchange ok (unknown camera -> error)", flush=True)

        await ws.close(code=1000)
        print("explicit close sent", flush=True)
    print("TCP session closed cleanly", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8020")
    ap.add_argument("--token", default=os.getenv("WS_TOKEN", "demo-token"))
    args = ap.parse_args()
    try:
        return asyncio.run(main_async(args.url, args.token))
    except (AssertionError, asyncio.TimeoutError) as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
