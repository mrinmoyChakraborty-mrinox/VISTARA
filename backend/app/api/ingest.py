"""Shared frame-ingestion path for every WebSocket camera input.

Browser, phone (QR-paired), and gateway frames all land here, so validation,
sampling, gate, buffer, and backpressure behave identically. The wire contract
is unchanged; `seq` is optional and advisory.

Returns small result dicts; never raises on client data (only on bugs).
"""

from __future__ import annotations

import base64
import binascii
import time
from dataclasses import dataclass

from backend.app.cameras.frames import FrameValidationError, validate_frame_array
from backend.app.cameras.manager import manager
from backend.app.core.config import settings
from backend.app.core.logging import log_event
from backend.app.perception.pipeline import build_event_payload, frame_to_bgr


@dataclass
class IngestSession:
    """Per-connection ingest state: sequence tracking + sampling guard."""

    camera_id: str
    user_id: str
    last_seq: int = 0
    last_accept_ts: float = 0.0
    accepted: int = 0
    dropped_fps: int = 0
    dropped_invalid: int = 0
    seq_gaps: int = 0
    errors_sent: int = 0

    def check_sample_gate(self, now: float) -> bool:
        if settings.ingest_max_fps <= 0:
            self.last_accept_ts = now
            return True  # sampling disabled (tests / unlimited ingest)
        min_interval = 1.0 / max(settings.ingest_max_fps, 0.1)
        if now - self.last_accept_ts < min_interval:
            self.dropped_fps += 1
            return False
        self.last_accept_ts = now
        return True

    def check_seq(self, seq) -> str | None:
        """Returns an error string for duplicates, or None. Counts gaps."""
        if seq is None:
            return None
        try:
            seq = int(seq)
        except (TypeError, ValueError):
            return "invalid seq (must be an integer)"
        if seq <= 0:
            return "invalid seq (must be positive)"
        if seq <= self.last_seq:
            return f"duplicate/out-of-order frame ignored (seq={seq})"
        if self.last_seq and seq > self.last_seq + 1:
            self.seq_gaps += seq - self.last_seq - 1
        self.last_seq = seq
        return None


def decode_frame_data(data) -> tuple[bytes | None, str | None]:
    """Base64 + size validation. Returns (jpeg, error)."""
    if not isinstance(data, str) or not data:
        return None, "missing frame data"
    max_b64 = settings.ws_max_frame_bytes * 4 // 3 + 64
    if len(data) > max_b64:
        return None, f"frame payload exceeds {settings.ws_max_frame_bytes} bytes"
    try:
        jpeg = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        return None, "malformed base64 frame data"
    if len(jpeg) > settings.ws_max_frame_bytes:
        return None, f"frame exceeds {settings.ws_max_frame_bytes} bytes"
    if len(jpeg) < 128:
        return None, "frame too small to be a JPEG"
    return jpeg, None


def ingest_bgr(
    runtime,
    bgr,
    *,
    user_id: str,
    camera_id: str,
    now: float | None = None,
    count_frame: bool = True,
    offer: bool = True,
) -> dict:
    """Shared gate→buffer→offer core for every source type.

    WS callers validate/decode first, then call this. Pull sources call this
    from their on_frame bridge (with count_frame=False, already counted).
    offer=False still pushes to the buffer and runs the gate (scores feed the
    baseline stability check) but never enqueues a normal change context —
    used while the initial baseline is not ready yet.
    Returns {"ok": True, "fired": bool, "score": float} or {"ok","error"} — never raises.
    """
    now = now if now is not None else time.monotonic()
    if count_frame:
        runtime.source.note_frame()
    runtime.buffer.push(bgr, now)
    runtime.frames_ingested += 1

    decision = runtime.gate.update(bgr, now)
    if not decision.fired:
        return {"ok": True, "fired": False, "score": round(decision.score, 4)}

    log_event(
        "change_detected",
        status="ok",
        user_id=user_id,
        camera_id=camera_id,
        extra={"score": round(decision.score, 4)},
    )
    ctx = build_event_payload(runtime.buffer)
    if ctx is None:
        return {"ok": True, "fired": True, "score": round(decision.score, 4)}
    ctx.camera_id = camera_id
    ctx.user_id = user_id
    ctx.score = decision.score
    if not offer:
        return {"ok": True, "fired": True, "score": round(decision.score, 4)}
    queued = manager.offer_event(runtime, ctx)
    if not queued:
        log_event(
            "camera_frame_dropped",
            status="dropped",
            user_id=user_id,
            camera_id=camera_id,
        )
    return {"ok": True, "fired": True, "score": round(decision.score, 4)}


def ingest_jpeg(
    runtime,
    session: IngestSession,
    jpeg: bytes,
    now: float | None = None,
    offer: bool = True,
) -> dict:
    """Validate -> normalize -> buffer -> gate -> bounded event offer.

    Returns {"ok": True, "fired": bool, "score": float} or {"ok": False, "error": str}.
    """
    now = now if now is not None else time.monotonic()
    try:
        bgr = frame_to_bgr(jpeg)
    except ValueError as exc:
        session.dropped_invalid += 1
        return {"ok": False, "error": f"undecodable JPEG: {exc}"}
    try:
        validate_frame_array(bgr, max_dim=settings.ws_max_image_dim)
    except FrameValidationError as exc:
        session.dropped_invalid += 1
        return {"ok": False, "error": str(exc)}

    session.accepted += 1
    return ingest_bgr(
        runtime,
        bgr,
        user_id=session.user_id,
        camera_id=session.camera_id,
        now=now,
        offer=offer,
    )


def ingest_pull_frame(runtime, nframe, user_id: str, offer: bool = True) -> dict:
    """Bridge for pull sources (RTSP/HLS/MJPEG): NormalizedFrame -> shared pipeline."""
    return ingest_bgr(
        runtime,
        nframe.frame,
        user_id=user_id,
        camera_id=nframe.camera_id,
        now=nframe.timestamp,
        count_frame=False,
        offer=offer,
    )
