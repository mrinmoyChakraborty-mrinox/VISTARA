"""Perception pipeline: gate -> rolling buffer -> VLM -> memory -> evidence.

The camera loop stays independent of slow VLM inference: frames are pushed to a
queue and a worker consumes them. Payload = 1 high-res current frame + 1-2 low-res
context frames + change-region crop (Stage 4 requirement).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from backend.app.core.config import settings
from backend.app.memory.schemas import VLMPerception
from backend.app.memory.service import MemoryService, SceneState
from backend.app.perception.buffer import BufferedFrame, RollingBuffer
from backend.app.perception.gate import change_bbox, to_gray_small
from backend.app.perception.image_utils import (
    extract_crop_jpeg,
    map_bbox_to_full,
    prepare_frame_jpeg,
)


@dataclass
class EventContext:
    camera_id: str
    user_id: str
    timestamp: datetime
    main_jpeg: bytes
    context_jpegs: list[bytes] = field(default_factory=list)
    crop_jpeg: bytes | None = None
    score: float = 0.0


def build_event_payload(buffer: RollingBuffer) -> EventContext | None:
    """Select representative frames and assemble the VLM payload + crop."""
    frames = buffer.snapshot()
    if not frames:
        return None

    representative = RollingBuffer.select_representative(frames, count=3)
    current = representative[-1]
    earlier = representative[:-1] or [current]

    main_jpeg, _, _ = prepare_frame_jpeg(
        current.frame, settings.vlm_main_max_side, settings.vlm_jpeg_quality
    )
    context_jpegs = []
    for bf in earlier[-2:]:  # 1-2 lower-res context frames
        jpeg, _, _ = prepare_frame_jpeg(
            bf.frame, settings.vlm_context_max_side, settings.vlm_jpeg_quality
        )
        context_jpegs.append(jpeg)

    crop_jpeg = None
    if len(representative) >= 2:
        prev_frame = representative[0].frame
        ga, gb = to_gray_small(prev_frame), to_gray_small(current.frame)
        bbox_small = change_bbox(ga, gb, padding_px=8)
        if bbox_small is not None:
            h, w = current.frame.shape[:2]
            bbox_full = map_bbox_to_full(
                bbox_small,
                (ga.shape[1], ga.shape[0]),
                (w, h),
                padding_px=settings.vlm_crop_padding_px,
            )
            try:
                crop_jpeg, _ = extract_crop_jpeg(
                    current.frame,
                    bbox_full,
                    settings.vlm_crop_max_side,
                    settings.vlm_jpeg_quality,
                )
            except ValueError:
                crop_jpeg = None

    # Order: high-res current first, then context, then crop.
    return EventContext(
        camera_id="",
        user_id="",
        timestamp=datetime.now(timezone.utc),
        main_jpeg=main_jpeg,
        context_jpegs=context_jpegs,
        crop_jpeg=crop_jpeg,
    )


def payload_images(ctx: EventContext) -> list[bytes]:
    frames = [ctx.main_jpeg, *ctx.context_jpegs]
    if ctx.crop_jpeg:
        frames.append(ctx.crop_jpeg)
    return frames


def make_previous_state(
    memory_service: MemoryService, user_id: str, camera_id: str
) -> SceneState:
    """Load the previous semantic state (last memory's objects) for delta comparison."""
    state = SceneState()
    latest = memory_service.memories.latest(user_id, camera_id)
    if latest is not None:
        from backend.app.memory.normalization import normalize_name

        for obj in latest.objects:
            state.locations[normalize_name(obj.name)] = obj.location
    return state


def frame_to_bgr(jpeg: bytes) -> np.ndarray:
    import cv2

    arr = np.frombuffer(jpeg, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode JPEG frame")
    return img


# Re-export for convenience/tests.
__all__ = [
    "EventContext",
    "build_event_payload",
    "payload_images",
    "make_previous_state",
    "frame_to_bgr",
    "MemoryService",
    "SceneState",
    "VLMPerception",
    "BufferedFrame",
]
