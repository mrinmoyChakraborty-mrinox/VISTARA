"""Perception gate — cheap local OpenCV change detection (no AI model).

Answers exactly one question: should the expensive VLM wake up?
Uses resize -> grayscale -> absolute frame difference -> optional SSIM ->
persistence check -> cooldown.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

GATE_SIZE = (160, 120)


@dataclass
class GateConfig:
    change_threshold: float = 0.02
    cooldown_seconds: float = 8.0
    persistence_frames: int = 2
    use_ssim: bool = False
    ssim_threshold: float = 0.90


@dataclass
class GateDecision:
    fired: bool
    score: float
    reason: str
    consecutive: int = 0


def to_gray_small(
    frame_bgr: np.ndarray, size: tuple[int, int] = GATE_SIZE
) -> np.ndarray:
    small = cv2.resize(frame_bgr, size, interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)


def frame_change_score(a_gray: np.ndarray, b_gray: np.ndarray) -> float:
    diff = cv2.absdiff(a_gray, b_gray)
    return float(np.mean(diff)) / 255.0


def _ssim_score(a_gray: np.ndarray, b_gray: np.ndarray) -> float:
    """Compact SSIM (no scikit-image dependency)."""
    a = a_gray.astype(np.float64)
    b = b_gray.astype(np.float64)
    mu_a, mu_b = a.mean(), b.mean()
    var_a, var_b = a.var(), b.var()
    cov = ((a - mu_a) * (b - mu_b)).mean()
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    denom = (mu_a**2 + mu_b**2 + c1) * (var_a + var_b + c2)
    if denom == 0:
        return 1.0
    return float(((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / denom)


class PerceptionGate:
    """Stateful gate. Feed frames in; ask whether the moment is worth a VLM call."""

    def __init__(self, config: GateConfig | None = None):
        self.config = config or GateConfig()
        self._prev: np.ndarray | None = None
        self._consecutive = 0
        self._cooldown_until = 0.0

    def reset(self) -> None:
        self._prev = None
        self._consecutive = 0

    def update(self, frame_bgr: np.ndarray, now: float) -> GateDecision:
        gray = to_gray_small(frame_bgr)
        if self._prev is None:
            self._prev = gray
            return GateDecision(False, 0.0, "warming_up")

        score = frame_change_score(self._prev, gray)
        self._prev = gray

        if now < self._cooldown_until:
            return GateDecision(False, score, "cooldown", self._consecutive)

        if self.config.use_ssim:
            if (
                _ssim_score(self._prev, gray) > self.config.ssim_threshold
                and score < self.config.change_threshold
            ):
                self._consecutive = 0
                return GateDecision(False, score, "ssim_similar", 0)

        if score >= self.config.change_threshold:
            self._consecutive += 1
            if self._consecutive >= self.config.persistence_frames:
                self._consecutive = 0
                self._cooldown_until = now + self.config.cooldown_seconds
                return GateDecision(True, score, "changed", 0)
            return GateDecision(False, score, "persistence", self._consecutive)

        self._consecutive = 0
        return GateDecision(False, score, "unchanged", 0)


def change_bbox(
    a_gray: np.ndarray,
    b_gray: np.ndarray,
    padding_px: int = 8,
    min_area_ratio: float = 0.002,
) -> tuple[int, int, int, int] | None:
    """Bounding box (x, y, w, h) of the largest changed region in gate coords."""
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
    x0, y0 = max(0, x - padding_px), max(0, y - padding_px)
    x1, y1 = min(W, x + w + padding_px), min(H, y + h + padding_px)
    return (x0, y0, x1 - x0, y1 - y0)
