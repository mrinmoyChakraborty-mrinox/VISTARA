"""RTSP network-camera source (real implementation over the FFmpeg transport).

URL is untrusted input: validated against the SSRF policy on connect and NEVER
logged in full (redacted). Credentials stay in server-side config only.
"""

from __future__ import annotations

import numpy as np

from backend.app.cameras.ffmpeg_reader import (
    FFmpegFrameReader,
    TransportError,
    ffmpeg_binary,
)
from backend.app.cameras.frames import NormalizedFrame, make_normalized_frame
from backend.app.cameras.pull import PullCameraSource
from backend.app.cameras.security import redact_url, validate_stream_url


class RTSPCameraSource(PullCameraSource):
    source_kind = "rtsp"

    def __init__(self, *args, allow_private_networks: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self._allow_private = allow_private_networks
        self._reader: FFmpegFrameReader | None = None
        self._seq = 0

    @property
    def url(self) -> str:
        return str(
            self.metadata.config.get("url")
            or self.metadata.config.get("stream_url")
            or ""
        )

    @property
    def redacted_url(self) -> str:
        return redact_url(self.url)

    def _extra_input(self) -> list[str]:
        return []

    def _do_connect(self) -> None:
        validate_stream_url(self.url, allow_private_networks=self._allow_private)
        if ffmpeg_binary() is None and not self.metadata.config.get("_test_transport"):
            self.note_error("ffmpeg binary not found on PATH")
            from backend.app.cameras.base import CameraLifecycle

            self.transition(CameraLifecycle.FAILED)
            raise TransportError("ffmpeg binary not found on PATH")
        cfg = self.metadata.config
        self._reader = FFmpegFrameReader(
            self.url,
            width=int(cfg.get("width", 640)),
            height=int(cfg.get("height", 360)),
            fps=float(cfg.get("fps", 2.0)),
            transport=str(cfg.get("rtsp_transport", "tcp")),
            connect_timeout_s=float(cfg.get("connect_timeout_s", 8.0)),
            read_timeout_s=float(cfg.get("read_timeout_s", 10.0)),
            extra_input=self._extra_input(),
        )
        # Test seam: inject a fake transport without spawning ffmpeg.
        transport = cfg.get("_test_transport")
        if transport is not None:
            self._reader._proc_transport = transport
        try:
            self._reader.open()
        except TransportError as exc:
            self.note_error(str(exc))
            from backend.app.cameras.base import CameraLifecycle

            try:
                self.transition(CameraLifecycle.FAILED)
            except Exception:  # noqa: BLE001
                pass
            raise
        from backend.app.cameras.base import CameraLifecycle

        self.transition(CameraLifecycle.CONNECTED)
        self.capabilities.notes = f"rtsp via ffmpeg ({self.redacted_url})"

    def _do_close(self) -> None:
        super()._do_close()
        reader, self._reader = self._reader, None
        if reader is not None:
            reader.close()

    def open_transport(self) -> None:
        if self._reader is not None and not self._reader.running:
            try:
                self._reader.open()
            except TransportError as exc:
                self.note_error(str(exc))
                raise

    def close_transport(self) -> None:
        if self._reader is not None:
            self._reader.close()

    def read_frame(self) -> NormalizedFrame | None:
        if self._reader is None:
            return None
        bgr: np.ndarray | None = self._reader.read()
        if bgr is None:
            return None
        self._seq += 1
        return make_normalized_frame(
            self.metadata.id,
            bgr,
            source_metadata={"kind": "rtsp", "url": self.redacted_url},
        )
