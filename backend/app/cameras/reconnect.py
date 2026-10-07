"""Bounded exponential backoff with jitter for reconnect loops.

Schedule (defaults): 1s, 2s, 4s, 8s, 16s, 30s (max). Resets after a success.
Never busy-loops: every wait is awaited by the caller via .next_delay().
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class BackoffPolicy:
    base_seconds: float = 1.0
    factor: float = 2.0
    max_seconds: float = 30.0
    jitter_ratio: float = 0.2

    def __post_init__(self) -> None:
        self._attempt = 0

    @property
    def attempt(self) -> int:
        return self._attempt

    def next_delay(self) -> float:
        delay = min(self.base_seconds * (self.factor**self._attempt), self.max_seconds)
        self._attempt += 1
        if self.jitter_ratio > 0:
            jitter = delay * self.jitter_ratio
            delay = max(0.0, delay + random.uniform(-jitter, jitter))
        return delay

    def reset(self) -> None:
        self._attempt = 0


def backoff_schedule(
    policy: BackoffPolicy | None = None, steps: int = 6
) -> list[float]:
    """Deterministic schedule preview (jitter disabled) for tests/docs."""
    p = policy or BackoffPolicy()
    p.jitter_ratio = 0.0
    p.reset()
    return [round(p.next_delay(), 3) for _ in range(steps)]
