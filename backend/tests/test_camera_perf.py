"""Transport stress test (§21): 3 logical cameras, 10-15fps synthetic ingest.

Uses the REAL gate + buffer + bounded queues + mock VLM (no Groq).
Measures: ingest time, queue depth (bounded), dropped frames, worker stability.
"""

from __future__ import annotations

import asyncio
import time

import numpy as np

from backend.app.api.ingest import IngestSession, ingest_jpeg
from backend.app.cameras.manager import CameraManager
from backend.app.perception.gate import GateConfig


def _frame(i: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed * 1000 + i)
    img = np.full((240, 320, 3), 40, np.uint8)
    x = (i * 17) % 220
    img[80:160, x : x + 60] = (0, 200, 0)
    noise = rng.integers(0, 8, size=(240, 320, 1), dtype=np.uint8)
    return np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def test_three_camera_stress():
    async def go():
        from backend.app.core.config import settings

        settings.ingest_max_fps = 0.0  # unlimited: measure raw pipeline cost
        manager = CameraManager()
        runtimes = []
        sessions = []
        for n in range(3):
            rt = await manager.add(
                f"cam{n}",
                "u1",
                f"C{n}",
                "browser",
                {},
                event_queue_maxsize=4,
                gate_config=GateConfig(
                    change_threshold=0.005, persistence_frames=1, cooldown_seconds=0.0
                ),
            )
            runtimes.append(rt)
            sessions.append(IngestSession(camera_id=f"cam{n}", user_id="u1"))

        import cv2

        t0 = time.perf_counter()
        frames_per_cam = 40
        fired_total = 0
        for i in range(frames_per_cam):
            for n, (rt, sess) in enumerate(zip(runtimes, sessions)):
                ok, buf = cv2.imencode(".jpg", _frame(i, n))
                assert ok
                res = ingest_jpeg(rt, sess, bytes(buf), now=time.monotonic())
                assert res["ok"]
                fired_total += 1 if res["fired"] else 0
        wall = time.perf_counter() - t0

        total_ingested = sum(rt.frames_ingested for rt in runtimes)
        assert total_ingested == 3 * frames_per_cam
        for rt in runtimes:
            # Bounded: depth never exceeds maxsize; drops counted, never grown.
            assert rt.event_queue.qsize() <= 4
            health = manager.health(rt.source.metadata.id)
            assert health["frames_ingested"] == frames_per_cam
        fps = total_ingested / wall
        print(
            f"\nstress: {total_ingested} frames in {wall:.2f}s ({fps:.1f} fps), "
            f"gate fired {fired_total}x, queue drops "
            f"{sum(rt.frames_dropped_queue for rt in runtimes)}"
        )
        assert (
            fps > 15.0
        )  # gate+buffer must keep up well beyond the 2-5fps operating point

    asyncio.run(go())
