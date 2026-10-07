"""Hybrid retrieval scoring: metadata candidate set + optional vector rerank.

Vector search is NEVER the only mechanism. Metadata/object/time/event filters
produce a candidate set; semantic similarity only reorders that set.
"""

from __future__ import annotations

import math


def cosine_similarity(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def semantic_text(memory) -> str:
    """The text that the client-side embedding represents for a memory."""
    parts = [
        getattr(memory, "scene_type", ""),
        getattr(memory, "scene_summary", ""),
        getattr(memory, "activity", ""),
    ]
    for obj in getattr(memory, "objects", []) or []:
        parts.append(f"{obj.name} at {obj.location}")
    for ev in getattr(memory, "events", []) or []:
        parts.append(
            f"{ev.object_name} moved from {ev.from_location} to {ev.to_location}"
        )
    return ". ".join(p for p in parts if p)


def rerank_by_similarity(memories: list, query_vector: list[float] | None) -> list:
    """Stable rerank: memories with embeddings sort by similarity, others keep order."""
    if not query_vector:
        return memories
    scored = []
    for idx, m in enumerate(memories):
        sim = cosine_similarity(getattr(m, "embedding", None), query_vector)
        scored.append((sim, -idx, m))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [m for _, _, m in scored]
