"""RTSP/HLS failure handling (fake transport), manager supervision, WS ingest hardening."""

from __future__ import annotations

import asyncio

import numpy as np
import pytest

from backend.app.cameras.factory import create_source
from backend.app.cameras.ffmpeg_reader import FFmpegFrameReader, TransportError
from backend.app.cameras.manager import CameraManager


class FakeProc:
    def __init__(self, frames: list[bytes] | None = None, exit_code: int | None = None):
        self._frames = list(frames or [])
        self._exit_code = exit_code
        self.killed = False
        self.terminated = False

    def poll(self):
        if self._exit_code is not None and not self._frames:
            return self._exit_code
        return None if self._frames else self._exit_code

    @property
    def stdout(self):
        return self

    def read(self, n: int) -> bytes:
        if not self._frames:
            return b""
        chunk = self._frames.pop(0)
        return chunk[:n]

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return 0


class FakeTransport:
    def __init__(self, proc: FakeProc):
        self.proc = proc
        self.spawned: list[list[str]] = []

    def spawn(self, argv):
        self.spawned.append(argv)
        return self.proc

    def terminate(self, proc, grace_seconds=3.0):
        proc.terminate()


def _raw_frame(w=64, h=48, value=90) -> bytes:
    return np.full((h, w, 3), value, np.uint8).tobytes()


# --------------------------------------------------------------------- RTSP
def test_rtsp_rejects_ssrf_urls():
    src = create_source("c", "u", "n", "rtsp", {"url": "rtsp://127.0.0.1/x"})
    with pytest.raises(Exception):
        src.connect()


def test_rtsp_missing_binary_fails_cleanly():
    src = create_source("c", "u", "n", "rtsp", {"url": "rtsp://camera.example.com/x"})
    src._allow_private = True
    import backend.app.cameras.rtsp as rtsp_mod

    real = rtsp_mod.ffmpeg_binary
    rtsp_mod.ffmpeg_binary = lambda: None
    try:
        with pytest.raises(TransportError):
            src.connect()
    finally:
        rtsp_mod.ffmpeg_binary = real
    assert "ffmpeg" in src.metrics.last_error


def test_rtsp_reads_frames_via_fake_transport():
    proc = FakeProc(frames=[_raw_frame(640, 360), _raw_frame(640, 360)])
    src = create_source(
        "c",
        "u",
        "n",
        "rtsp",
        {"url": "rtsp://camera.example.com/x", "_test_transport": FakeTransport(proc)},
    )
    src._allow_private = True
    src.connect()
    frame = src.read_frame()
    assert frame is not None and (frame.width, frame.height) == (640, 360)
    src.close()


def test_rtsp_immediate_exit_is_surfaced():
    proc = FakeProc(frames=[], exit_code=1)
    src = create_source(
        "c",
        "u",
        "n",
        "rtsp",
        {"url": "rtsp://camera.example.com/x", "_test_transport": FakeTransport(proc)},
    )
    src._allow_private = True
    with pytest.raises(TransportError):
        src.connect()
    src.close()  # never raises, no leak


def test_hls_registers_and_redacts():
    src = create_source("c", "u", "n", "hls", {"url": "https://example.com/live.m3u8"})
    assert src.source_kind == "hls"
    assert "https://example.com" in src.redacted_url


def test_reader_short_read_tolerated():
    proc = FakeProc(frames=[b"short"])
    reader = FFmpegFrameReader(
        "rtsp://h/x", width=64, height=48, process_transport=FakeTransport(proc)
    )
    # open() would sleep+check; exercise read() path directly instead.
    reader._proc = proc
    assert reader.read() is None
    reader.close()


# -------------------------------------------------------------------- manager
def test_manager_bounded_queue_drops_oldest():
    async def go():
        m = CameraManager()
        rt = await m.add("c", "u", "n", "browser", {}, event_queue_maxsize=2)
        assert m.offer_event(rt, "a") and m.offer_event(rt, "b")
        assert m.offer_event(rt, "c")  # full -> drops oldest, keeps newest
        assert rt.frames_dropped_queue == 1
        got = [rt.event_queue.get_nowait(), rt.event_queue.get_nowait()]
        assert got == ["b", "c"]
        assert m.health("c")["queue_depth"] == 0
        assert m.health("nope") is None

    asyncio.run(go())


def test_manager_supervision_isolates_crashes():
    async def go():
        m = CameraManager()
        rt = await m.add("c", "u", "n", "browser", {})

        async def boom():
            raise RuntimeError("camera blew up")

        async def fine():
            await asyncio.sleep(0.05)
            return "ok"

        t1 = m.supervise(boom, "c")
        t2 = m.supervise(fine, "c")
        await asyncio.gather(t1, t2)
        assert "blew up" in rt.last_error

    asyncio.run(go())


def test_manager_stale_detection():
    async def go():
        m = CameraManager()
        rt = await m.add("c", "u", "n", "browser", {})
        assert m.is_stale("c") is False  # never connected, never ran
        rt.source.mark_connected()
        assert m.is_stale("c", after_seconds=30.0) is True  # connected, no frames
        rt.source.note_frame()
        assert m.is_stale("c", after_seconds=30.0) is False

    asyncio.run(go())
