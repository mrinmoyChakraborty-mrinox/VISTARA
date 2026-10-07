"""MJPEG source: multipart/x-mixed-replace parsing over HTTP.

Pure Python (httpx streaming). Malformed segments are skipped; a malformed
stream can never wedge the worker — consecutive failures trigger the standard
pull-loop reconnect path. Frame size caps and JPEG SOI/EOI validation apply.
"""

from __future__ import annotations

import re
import time

import cv2
import httpx
import numpy as np

from backend.app.cameras.frames import NormalizedFrame, make_normalized_frame
from backend.app.cameras.pull import PullCameraSource
from backend.app.cameras.security import redact_url, validate_stream_url

JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"
DEFAULT_MAX_FRAME_BYTES = 8 * 1024 * 1024


def split_mjpeg_chunks(buffer: bytes, boundary: bytes) -> tuple[list[bytes], bytes]:
    """Split complete parts off a buffer. Returns (parts, remainder)."""
    parts: list[bytes] = []
    marker = b"--" + boundary
    while True:
        start = buffer.find(marker)
        if start < 0:
            break
        nxt = buffer.find(marker, start + len(marker))
        if nxt < 0:
            break
        parts.append(buffer[start:nxt])
        buffer = buffer[nxt:]
    return parts, buffer


def extract_jpeg(part: bytes, max_bytes: int = DEFAULT_MAX_FRAME_BYTES) -> bytes | None:
    """Extract and validate one JPEG from a multipart part. None if malformed."""
    header_end = part.find(b"\r\n\r\n")
    if header_end < 0:
        return None
    body = part[header_end + 4 :].strip(b"\r\n-")
    if len(body) > max_bytes or len(body) < 128:
        return None
    start = body.find(JPEG_SOI)
    end = body.rfind(JPEG_EOI)
    if start < 0 or end <= start:
        return None
    return body[start : end + 2]


def parse_content_type_boundary(content_type: str) -> bytes | None:
    m = re.search(r"boundary=([^;,\s]+)", content_type or "", re.IGNORECASE)
    if not m:
        return None
    return m.group(1).strip('"').encode("latin-1")


class MJPEGCameraSource(PullCameraSource):
    source_kind = "mjpeg"

    def __init__(self, *args, allow_private_networks: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self._allow_private = allow_private_networks
        self._client: httpx.Client | None = None
        self._stream = None
        self._chunks = None
        self._buffer = b""
        self._boundary: bytes | None = None
        self._max_frame_bytes = int(
            (self.metadata.config.get("max_frame_bytes") or DEFAULT_MAX_FRAME_BYTES)
        )

    @property
    def url(self) -> str:
        return str(self.metadata.config.get("url") or "")

    def _do_connect(self) -> None:
        from backend.app.cameras.base import CameraLifecycle

        validate_stream_url(self.url, allow_private_networks=self._allow_private)
        cfg = self.metadata.config
        timeout = httpx.Timeout(
            float(cfg.get("connect_timeout_s", 8.0)),
            read=float(cfg.get("read_timeout_s", 10.0)),
        )
        self._client = httpx.Client(
            timeout=timeout, follow_redirects=False, max_redirects=0
        )
        try:
            req = self._client.build_request("GET", self.url)
            resp = self._client.send(req, stream=True)
        except Exception as exc:
            self.note_error(f"mjpeg connect failed: {exc}")
            self._close_client()
            try:
                self.transition(CameraLifecycle.FAILED)
            except Exception:  # noqa: BLE001
                pass
            raise
        ctype = resp.headers.get("content-type", "")
        self._boundary = parse_content_type_boundary(ctype)
        if resp.status_code >= 400 or self._boundary is None:
            try:
                resp.close()
            except Exception:  # noqa: BLE001
                pass
            self._close_client()
            self.note_error(f"mjpeg bad response: status={resp.status_code}")
            try:
                self.transition(CameraLifecycle.FAILED)
            except Exception:  # noqa: BLE001
                pass
            from backend.app.cameras.ffmpeg_reader import TransportError

            raise TransportError(f"mjpeg bad response: status={resp.status_code}")
        self._stream = resp
        self._buffer = b""
        self._chunks = resp.iter_bytes(65536)
        try:
            self.transition(CameraLifecycle.CONNECTED)
        except Exception:  # noqa: BLE001
            pass
        self.capabilities.notes = "mjpeg multipart over http"

    def _do_close(self) -> None:
        super()._do_close()
        self._close_client()

    def _close_client(self) -> None:
        stream, self._stream = self._stream, None
        self._chunks = None
        if stream is not None:
            try:
                stream.close()
            except Exception:  # noqa: BLE001
                pass
        client, self._client = self._client, None
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass

    def open_transport(self) -> None:
        if self._stream is None:
            self._do_connect()

    def close_transport(self) -> None:
        self._close_client()

    def _decode_return(self, jpeg: bytes) -> NormalizedFrame | None:
        bgr = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if bgr is None:
            self.note_dropped()
            return None
        self._seq += 1
        return make_normalized_frame(
            self.metadata.id,
            bgr,
            source_metadata={"kind": "mjpeg", "url": redact_url(self.url)},
        )

    def read_frame(self) -> NormalizedFrame | None:
        if self._stream is None or self._boundary is None:
            return None
        deadline = time.monotonic() + 5.0
        while True:
            # Drain already-buffered complete parts before reading more.
            parts, self._buffer = split_mjpeg_chunks(self._buffer, self._boundary)
            for part in parts:
                jpeg = extract_jpeg(part, self._max_frame_bytes)
                if jpeg is None:
                    self.note_dropped()
                    continue
                frame = self._decode_return(jpeg)
                if frame is not None:
                    return frame
            if time.monotonic() > deadline:
                return None
            if self._chunks is None:
                return None
            try:
                chunk = next(self._chunks)
            except StopIteration:
                chunk = b""
            except Exception as exc:  # noqa: BLE001
                self.note_error(f"mjpeg read failed: {exc}")
                return None
            if not chunk:
                # Stream exhausted: flush any trailing bytes as a final part,
                # so a camera that closes after one part still yields it.
                jpeg = extract_jpeg(self._buffer, self._max_frame_bytes)
                self._buffer = b""
                if jpeg is None:
                    return None
                return self._decode_return(jpeg)
            self._buffer += chunk
            if len(self._buffer) > self._max_frame_bytes * 2:
                # Runaway buffer: resync rather than grow.
                self._buffer = self._buffer[-self._max_frame_bytes :]
                self.note_dropped()

    @property
    def redacted_url(self) -> str:
        return redact_url(self.url)
