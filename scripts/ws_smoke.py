"""Temporary WebSocket validation client (Phase 2, backend validation only).

Starts no frontend. Exercises the real /ws/cameras/{camera_id} flow:
connect -> connection_state -> frame submission -> change_detected ->
worker -> VLM -> memory creation -> memory_created.

Usage (mock mode, local server):
    $env:MOCK_MODE='true'
    python -m uvicorn backend.app.main:app --port 8000
    python scripts/ws_smoke.py --create-camera "Smoke cam" --frames test.jpeg

Auth: pass --token <jwt>, or WS_TOKEN env. In MOCK_MODE, "demo-token" works.
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


def rest_create_camera(base: str, token: str, name: str) -> str:
    req = urllib.request.Request(
        f"{base}/api/cameras",
        data=json.dumps({"name": name}).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.load(res)["id"]


def load_frames(paths: list[str], repeat: int = 2) -> list[bytes]:
    import cv2
    import numpy as np

    from backend.app.perception.image_utils import encode_jpeg

    frames: list[bytes] = []
    if paths:
        for p in paths:
            img = cv2.imread(p)
            if img is None:
                raise SystemExit(f"cannot read frame: {p}")
            frames.append(encode_jpeg(img, 85))
    else:
        base = np.full((240, 320, 3), 40, np.uint8)
        frames = []
        # Distinct positions each step so the diff gate sees continuous motion.
        for x in (40, 90, 140, 190, 240):
            img = base.copy()
            img[80:160, x : x + 60] = (0, 200, 0)
            frames.append(encode_jpeg(img, 85))
    while len(frames) < 2:
        frames.append(frames[-1])
    return (frames * repeat)[: max(2, len(frames))]


async def run(
    url: str, camera_id: str, token: str, frames: list[bytes], timeout_s: float
) -> int:
    import websockets

    ws_url = url.replace("http://", "ws://").replace("https://", "wss://")
    qs = urllib.parse.urlencode({"token": token})
    uri = f"{ws_url}/ws/cameras/{camera_id}?{qs}"
    print(f"connecting {ws_url}/ws/cameras/<id> ...")
    async with websockets.connect(uri, max_size=8 * 1024 * 1024) as ws:
        print(" <-", await asyncio.wait_for(ws.recv(), timeout_s))
        await ws.send(json.dumps({"type": "camera_connected"}))
        print(" -> camera_connected")
        print(" <-", await asyncio.wait_for(ws.recv(), timeout_s))

        import time

        for i, jpeg in enumerate(frames):
            # Pace at ~4fps so the server ingest sampler (default 5fps) accepts every frame.
            await asyncio.sleep(0.25)
            await ws.send(
                json.dumps(
                    {
                        "type": "frame",
                        "data": base64.b64encode(jpeg).decode(),
                        "ts": int(time.time() * 1000),
                    }
                )
            )
            print(f" -> frame {i + 1}/{len(frames)} ({len(jpeg) // 1024}KB)")

        deadline = asyncio.get_event_loop().time() + timeout_s
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                print("TIMEOUT waiting for memory_created")
                return 1
            msg = json.loads(await asyncio.wait_for(ws.recv(), remaining))
            print(" <-", msg.get("type"), str(msg)[:160])
            if msg.get("type") == "memory_created":
                print(f"\nSUCCESS: memory {msg.get('memory_id')}")
                return 0
            if msg.get("type") == "error":
                print("server error, continuing...")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--camera-id", default="")
    ap.add_argument("--create-camera", default="")
    ap.add_argument("--frames", nargs="*", default=[])
    ap.add_argument("--token", default=os.getenv("WS_TOKEN", "demo-token"))
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args()

    camera_id = args.camera_id
    if args.create_camera:
        camera_id = rest_create_camera(args.url, args.token, args.create_camera)
        print(f"created camera {camera_id}")
    if not camera_id:
        raise SystemExit("--camera-id or --create-camera is required")
    frames = load_frames(args.frames)
    return asyncio.run(run(args.url, camera_id, args.token, frames, args.timeout))


if __name__ == "__main__":
    raise SystemExit(main())
