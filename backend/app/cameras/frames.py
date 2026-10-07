"""Normalized frame contract: every source produces these; the pipeline knows no source types.

A NormalizedFrame carries a decoded BGR ndarray plus provenance. Source-specific
decoding (browser base64, RTSP/FFmpeg, HLS, MJPEG, gateway) lives in adapters and
must convert to this before touching the gate/buffer/worker.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

# Hard safety caps (independent of the tunable WS_* settings below).
ABSOLUTE_MAX_DIM = 4096
ABSOLUTE_MAX_BYTES = 15 * 1024 * 1024


@dataclass
class NormalizedFrame:
    camera_id: str
    timestamp: float  # monotonic seconds (ingest clock)
    frame: np.ndarray  # BGR uint8
    width: int
    height: int
    pixel_format: str = "bgr24"
    seq: int = 0  # per-camera sequence number (0 = unknown)
    client_ts: float | None = None  # sender wall-clock ms/1000 when provided
    # Source wall time (e.g. recorded-video media position mapped onto the demo
    # clock). None = live path, which keeps processing-time semantics exactly.
    source_ts: datetime | None = None
    source_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.height, self.width)


class FrameValidationError(ValueError):
    pass


def validate_frame_array(
    frame: np.ndarray,
    max_dim: int = ABSOLUTE_MAX_DIM,
    max_bytes: int = ABSOLUTE_MAX_BYTES,
) -> tuple[int, int]:
    """Validate a decoded BGR array. Returns (width, height). Raises FrameValidationError."""
    if not isinstance(frame, np.ndarray):
        raise FrameValidationError("frame is not an ndarray")
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise FrameValidationError(f"expected BGR image, got shape {frame.shape}")
    if frame.dtype != np.uint8:
        raise FrameValidationError(f"expected uint8, got {frame.dtype}")
    h, w = int(frame.shape[0]), int(frame.shape[1])
    if w <= 0 or h <= 0:
        raise FrameValidationError("zero-size frame")
    if max(w, h) > max_dim:
        raise FrameValidationError(f"frame {w}x{h} exceeds max dim {max_dim}")
    if frame.nbytes > max_bytes:
        raise FrameValidationError(f"frame bytes {frame.nbytes} exceed cap {max_bytes}")
    return w, h


def make_normalized_frame(
    camera_id: str,
    frame: np.ndarray,
    seq: int = 0,
    client_ts: float | None = None,
    source_ts: datetime | None = None,
    source_metadata: dict[str, Any] | None = None,
    now: float | None = None,
) -> NormalizedFrame:
    w, h = validate_frame_array(frame)
    return NormalizedFrame(
        camera_id=camera_id,
        timestamp=now if now is not None else time.monotonic(),
        frame=frame,
        width=w,
        height=h,
        seq=seq,
        client_ts=client_ts,
        source_ts=source_ts,
        source_metadata=dict(source_metadata or {}),
    )
