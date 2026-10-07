"""FFmpeg pull transport shared by RTSP and HLS sources.

- Spawns exactly one ffmpeg child per reader; kills it on close (no zombies).
- Connect/read timeouts via ffmpeg flags; corrupted output tolerated (skip, don't crash).
- FPS sampling + resolution normalization in ffmpeg (-vf fps,scale) so the
  backend never ingests full camera FPS at full resolution.
- Degrades gracefully when the ffmpeg binary is absent (clear FAILED state).

A ProcessTransport seam keeps this unit-testable without the binary or network.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from typing import Callable

import numpy as np


class TransportError(RuntimeError):
    pass


class ProcessTransport:
    """Thin seam around subprocess.Popen for testability."""

    def spawn(self, argv: list[str]) -> subprocess.Popen:
        return subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8
        )

    def terminate(self, proc: subprocess.Popen, grace_seconds: float = 3.0) -> None:
        if proc.poll() is not None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=grace_seconds)
        except Exception:  # noqa: BLE001 - cleanup must not raise
            pass


def ffmpeg_binary() -> str | None:
    return shutil.which("ffmpeg")


def build_argv(
    url: str,
    width: int,
    height: int,
    fps: float,
    transport: str = "tcp",
    connect_timeout_s: float = 8.0,
    read_timeout_s: float = 10.0,
    extra_input: list[str] | None = None,
) -> list[str]:
    us = int(connect_timeout_s * 1_000_000)
    argv = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        transport,
        "-stimeout",
        str(us),
        "-timeout",
        str(us),
        "-rw_timeout",
        str(int(read_timeout_s * 1_000_000)),
        *(extra_input or []),
        "-i",
        url,
        "-vf",
        f"fps={fps},scale={width}:{height}",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-an",
        "-sn",
        "-",
    ]
    return argv


class FFmpegFrameReader:
    """Reads normalized BGR frames from a stream URL via ffmpeg stdout."""

    def __init__(
        self,
        url: str,
        width: int = 640,
        height: int = 360,
        fps: float = 2.0,
        transport: str = "tcp",
        connect_timeout_s: float = 8.0,
        read_timeout_s: float = 10.0,
        extra_input: list[str] | None = None,
        process_transport: ProcessTransport | None = None,
        on_spawn: Callable[[list[str]], None] | None = None,
    ):
        self.url = url
        self.width = width
        self.height = height
        self.fps = fps
        self.transport = transport
        self.connect_timeout_s = connect_timeout_s
        self.read_timeout_s = read_timeout_s
        self.extra_input = extra_input or []
        self._proc_transport = process_transport or ProcessTransport()
        self._on_spawn = on_spawn
        self._proc: subprocess.Popen | None = None
        self._frame_bytes = width * height * 3
        self._lock = threading.Lock()
        self._consecutive_errors = 0

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def open(self) -> None:
        # Injected transports (tests) bypass the binary requirement; only the
        # default transport needs a real ffmpeg on PATH.
        if ffmpeg_binary() is None and type(self._proc_transport) is ProcessTransport:
            raise TransportError("ffmpeg binary not found on PATH")
        argv = build_argv(
            self.url,
            self.width,
            self.height,
            self.fps,
            self.transport,
            self.connect_timeout_s,
            self.read_timeout_s,
            self.extra_input,
        )
        # Never log argv with credentials; callers redact first.
        proc = self._proc_transport.spawn(argv)
        with self._lock:
            self._proc = proc
        if self._on_spawn:
            self._on_spawn(argv)
        # Fail fast if the child exits immediately (bad URL/auth).
        time.sleep(0.4)
        if proc.poll() not in (None,):
            self.close()
            raise TransportError(f"ffmpeg exited immediately (code {proc.poll()})")

    def read(self) -> np.ndarray | None:
        """Return one BGR frame, or None on timeout/corruption/exit (never raises)."""
        proc = self._proc
        if proc is None or proc.stdout is None:
            return None
        try:
            raw = proc.stdout.read(self._frame_bytes)
        except Exception:  # noqa: BLE001
            self._consecutive_errors += 1
            return None
        if proc.poll() is not None and not raw:
            return None
        if len(raw or b"") != self._frame_bytes:
            self._consecutive_errors += 1
            return None
        self._consecutive_errors = 0
        frame = np.frombuffer(raw, dtype=np.uint8).reshape((self.height, self.width, 3))
        return frame.copy()

    def close(self) -> None:
        with self._lock:
            proc, self._proc = self._proc, None
        if proc is not None:
            self._proc_transport.terminate(proc)

    def __enter__(self) -> "FFmpegFrameReader":
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
