"""Swappable provider interfaces (prompt requirement)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class VLMProvider(ABC):
    @abstractmethod
    def analyze(self, frames: list[bytes], **kwargs: Any) -> Any:
        """Analyze JPEG frame bytes -> validated perception. Implemented by Groq providers."""
        raise NotImplementedError


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> Any:
        raise NotImplementedError
