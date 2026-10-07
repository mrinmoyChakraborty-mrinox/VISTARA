"""Image prep + change-region crop for the VLM payload.

Stage 4 addition: when the OpenCV gate fires, compute the bounding box of the
changed region from the diff mask (with padding), map it to the full-resolution
frame, and add that crop as an additional image. Payload:
  1 high-res current frame (VLM_MAIN_MAX_SIDE)
+ 1-2 lower-res earlier context frames (VLM_CONTEXT_MAX_SIDE)
+ change-region crop (VLM_CROP_MAX_SIDE)

All max-side values + JPEG quality come from env (see config.Settings).
"""

from __future__ import annotations

import cv2
import numpy as np


def resize_to_max_side(img: np.ndarray, max_side: int) -> np.ndarray:
    h, w = img.shape[:2]
    m = max(h, w)
    if m <= max_side or m == 0:
        return img
    scale = max_side / float(m)
    return cv2.resize(
        img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
    )


def encode_jpeg(img_bgr: np.ndarray, quality: int = 85) -> bytes:
    ok, buf = cv2.imencode(
        ".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
    )
    if not ok:
        raise ValueError("JPEG encode failed")
    return bytes(buf)


def prepare_frame_jpeg(
    frame_bgr: np.ndarray, max_side: int, quality: int = 85
) -> tuple[bytes, int, int]:
    """Downscale to max_side, JPEG-encode. Returns (jpeg_bytes, out_w, out_h)."""
    small = resize_to_max_side(frame_bgr, max_side)
    h, w = small.shape[:2]
    return encode_jpeg(small, quality), w, h


def small_gray(frame_bgr: np.ndarray, size: tuple[int, int] = (160, 120)) -> np.ndarray:
    small = cv2.resize(frame_bgr, size, interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)


def frame_change_score(a_gray: np.ndarray, b_gray: np.ndarray) -> float:
    diff = cv2.absdiff(a_gray, b_gray)
    return float(np.mean(diff)) / 255.0


def change_bbox_from_mask(
    a_gray: np.ndarray,
    b_gray: np.ndarray,
    change_threshold: float = 0.12,
    padding_px: int = 8,
    min_area_ratio: float = 0.002,
) -> tuple[int, int, int, int] | None:
    """Bounding box (x, y, w, h) of the changed region in mask coords, or None.

    Uses the same absdiff signal as the gate: threshold the diff, clean with
    morphology, keep the largest contour above min_area_ratio.
    """
    diff = cv2.absdiff(a_gray, b_gray)
    _, mask = cv2.threshold(diff, int(255 * 0.15), 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    area_min = a_gray.size * min_area_ratio
    big = [c for c in contours if cv2.contourArea(c) >= area_min]
    if not big:
        return None
    x, y, w, h = cv2.boundingRect(max(big, key=cv2.contourArea))
    H, W = a_gray.shape[:2]
    # Also require the overall change score to clear the gate threshold.
    if frame_change_score(a_gray, b_gray) < change_threshold:
        return None
    x0 = max(0, x - padding_px)
    y0 = max(0, y - padding_px)
    x1 = min(W, x + w + padding_px)
    y1 = min(H, y + h + padding_px)
    return (x0, y0, x1 - x0, y1 - y0)


def map_bbox_to_full(
    bbox_small: tuple[int, int, int, int],
    small_shape: tuple[int, int],
    full_shape: tuple[int, int],
    padding_px: int = 24,
) -> tuple[int, int, int, int]:
    """Map a bbox from gate-mask coords to full-resolution frame coords (+padding)."""
    x, y, w, h = bbox_small
    small_w, small_h = small_shape
    full_w, full_h = full_shape
    sx = full_w / float(small_w)
    sy = full_h / float(small_h)
    x0 = max(0, int(x * sx) - padding_px)
    y0 = max(0, int(y * sy) - padding_px)
    x1 = min(full_w, int((x + w) * sx) + padding_px)
    y1 = min(full_h, int((y + h) * sy) + padding_px)
    return (x0, y0, max(1, x1 - x0), max(1, y1 - y0))


def extract_crop_jpeg(
    full_frame_bgr: np.ndarray,
    bbox_full: tuple[int, int, int, int],
    max_side: int,
    quality: int = 85,
) -> tuple[bytes, tuple[int, int, int, int]]:
    x, y, w, h = bbox_full
    crop = full_frame_bgr[y : y + h, x : x + w]
    if crop.size == 0:
        raise ValueError("Crop bbox is empty")
    small = resize_to_max_side(crop, max_side)
    return encode_jpeg(small, quality), bbox_full


def tile_frames_horizontal(frames_bgr_or_jpeg: list, max_h: int = 512) -> bytes:
    """Tiling fallback: stitch frames side-by-side into ONE JPEG.

    Accepts decoded BGR arrays or JPEG bytes. Used only if the provider
    rejects multi-image requests.
    """
    import cv2 as _cv2

    decoded = []
    for f in frames_bgr_or_jpeg:
        if isinstance(f, (bytes, bytearray)):
            img = _cv2.imdecode(np.frombuffer(bytes(f), np.uint8), _cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Could not decode JPEG for tiling")
            decoded.append(img)
        else:
            decoded.append(f)
    norm = []
    for img in decoded:
        h, w = img.shape[:2]
        if h > max_h:
            img = _cv2.resize(
                img, (int(w * max_h / h), max_h), interpolation=_cv2.INTER_AREA
            )
        norm.append(img)
    h_max = max(i.shape[0] for i in norm)
    padded = []
    for img in norm:
        if img.shape[0] < h_max:
            pad = h_max - img.shape[0]
            img = _cv2.copyMakeBorder(img, 0, pad, 0, 0, _cv2.BORDER_CONSTANT)
        padded.append(img)
    tiled = _cv2.hconcat(padded)
    return encode_jpeg(tiled, 85)
