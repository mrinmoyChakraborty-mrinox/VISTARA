"""Rolling frame buffer + representative frame selection."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

import numpy as np


@dataclass
class BufferedFrame:
    frame: np.ndarray
    ts: float
    # Source wall time when the producer knows it (recorded video); None keeps
    # live processing-time semantics exactly.
    source_ts: datetime | None = None


class RollingBuffer:
    """Fixed-size deque of recent frames, independent of VLM latency."""

    def __init__(self, maxlen: int = 30):
        self._frames: deque[BufferedFrame] = deque(maxlen=maxlen)

    def __len__(self) -> int:
        return len(self._frames)

    def push(self, frame: np.ndarray, ts: float, source_ts=None) -> None:
        self._frames.append(BufferedFrame(frame=frame, ts=ts, source_ts=source_ts))

    def snapshot(self) -> list[BufferedFrame]:
        return list(self._frames)

    def recent(self, n: int) -> list[BufferedFrame]:
        if n <= 0:
            return []
        return list(self._frames)[-n:]

    @staticmethod
    def select_representative(
        frames: list[BufferedFrame], count: int = 3
    ) -> list[BufferedFrame]:
        """Pick evenly spaced frames (first..last) as temporal context."""
        if not frames:
            return []
        if len(frames) <= count:
            return frames
        idx = np.linspace(0, len(frames) - 1, count).round().astype(int)
        seen: set[int] = set()
        out: list[BufferedFrame] = []
        for i in idx:
            if int(i) not in seen:
                seen.add(int(i))
                out.append(frames[int(i)])
        return out
