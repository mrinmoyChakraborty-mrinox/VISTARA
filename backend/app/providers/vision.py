"""Vision provider abstraction (swappable per ARCHITECTURE §29)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from backend.app.memory.schemas import VLMPerception


@dataclass
class VisionResult:
    perception: VLMPerception
    model: str
    latency_ms: float
    used_fallback: bool = False
    used_tiling: bool = False
    payload_bytes: int = 0
    raw: str = ""
    headers: dict = field(default_factory=dict)


class VisionProvider(ABC):
    @abstractmethod
    def analyze(
        self, frames: list[bytes], previous_state: dict | None = None
    ) -> VisionResult:
        """Validate and return structured perception for a contextual frame burst."""
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError
