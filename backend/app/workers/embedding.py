"""Embedding abstraction. The primary path is CLIENT-SIDE (browser).

The backend only stores the vector the browser computes. An optional server-side
fallback can be added later by implementing this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

EMBEDDING_DIM = 1024


def validate_embedding(vector: list[float]) -> None:
    if len(vector) != EMBEDDING_DIM:
        raise ValueError(
            f"Embedding must be {EMBEDDING_DIM}-dimensional, got {len(vector)}."
        )
    if any(not isinstance(x, (int, float)) for x in vector):
        raise ValueError("Embedding must contain only numbers.")


class EmbeddingProvider(ABC):
    """Optional server-side embedding fallback. NOT used for the primary browser path."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class NoopEmbeddingProvider(EmbeddingProvider):
    @property
    def dimension(self) -> int:
        return EMBEDDING_DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(
            "Server-side embeddings are disabled; embeddings are produced client-side."
        )
