"""RetrievalService: the single service layer the agent/chat code calls.

No raw SQL outside repositories. Every method takes user_id (from auth) and only
returns that user's data. Provenance wording: "last observed", never certain absence.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.app.core.logging import log_event
from backend.app.db.repositories import (
    CameraRepository,
    EvidenceRepository,
    MemoryEventRepository,
    MemoryObjectRepository,
    MemoryRepository,
    ObjectHistoryRepository,
)
from backend.app.memory.normalization import normalize_name, object_key
from backend.app.memory.serialize import event_to_out, memory_to_out
from backend.app.retrieval.hybrid import rerank_by_similarity


def _window(start: datetime | None, end: datetime | None, default_minutes: int = 60):
    now = datetime.now(timezone.utc)
    if start is None and end is None:
        end = now
        start = now - timedelta(minutes=default_minutes)
    return start, end


class RetrievalService:
    def __init__(self, db: Session, embedding_provider=None):
        self.db = db
        self.memories = MemoryRepository(db)
        self.events = MemoryEventRepository(db)
        self.objects = MemoryObjectRepository(db)
        self.history = ObjectHistoryRepository(db)
        self.evidence = EvidenceRepository(db)
        self.cameras = CameraRepository(db)
        self.embedding_provider = embedding_provider  # optional server-side fallback

    # --------------------------------------------------------------- memories
    def search_memory(
        self,
        user_id: str,
        query: str = "",
        camera_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 8,
        query_vector: list[float] | None = None,
    ) -> list:
        log_event(
            "retrieval_started",
            status="ok",
            user_id=user_id,
            extra={"tool": "search_memory"},
        )
        candidates = list(
            self.memories.list(
                user_id, camera_id=camera_id, start=start_time, end=end_time, limit=200
            )
        )
        if query:
            q = query.lower()
            q_norm = normalize_name(query)
            filtered = []
            for m in candidates:
                obj_names = " ".join(o.normalized_name for o in m.objects).lower()
                text = f"{m.scene_type} {m.scene_summary} {m.activity}".lower()
                if q_norm in obj_names or any(
                    tok in obj_names or tok in text for tok in q.split()
                ):
                    filtered.append(m)
            candidates = filtered or candidates

        if query_vector is None and self.embedding_provider is not None and query:
            query_vector = self.embedding_provider.embed([query])[0]
        candidates = rerank_by_similarity(candidates, query_vector)
        results = [memory_to_out(m) for m in candidates[:limit]]
        log_event(
            "retrieval_completed",
            status="ok",
            user_id=user_id,
            extra={"count": len(results)},
        )
        return results

    def get_scene(
        self,
        user_id: str,
        timestamp: datetime | None = None,
        camera_id: str | None = None,
    ):
        if timestamp is not None:
            before = self.memories.list(
                user_id, camera_id=camera_id, end=timestamp, limit=200
            )
            after = self.memories.list(
                user_id, camera_id=camera_id, start=timestamp, limit=200
            )
            pool = before + after
            pool.sort(key=lambda m: abs((m.timestamp - timestamp).total_seconds()))
            memory = pool[0] if pool else None
        else:
            memory = self.memories.latest(user_id, camera_id=camera_id)
        return memory_to_out(memory) if memory else None

    def get_memory(self, user_id: str, memory_id: str):
        memory = self.memories.get(user_id, memory_id)
        return memory_to_out(memory) if memory else None

    # ---------------------------------------------------------------- events
    def get_events(
        self,
        user_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_type: str | None = None,
        object_name: str | None = None,
        camera_id: str | None = None,
        limit: int = 50,
    ):
        start, end = _window(start_time, end_time)
        rows = self.events.list(
            user_id,
            start=start,
            end=end,
            event_type=event_type,
            object_name=object_name,
            camera_id=camera_id,
            limit=limit,
        )
        return [event_to_out(e) for e in rows]

    # -------------------------------------------------------- object history
    def get_object_history(
        self,
        user_id: str,
        object_name: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> dict:
        key = object_key(object_name)
        rows = list(self.history.list(user_id, key, limit=limit))
        if start_time:
            rows = [r for r in rows if r.timestamp >= start_time]
        if end_time:
            rows = [r for r in rows if r.timestamp <= end_time]
        return {
            "object": normalize_name(object_name),
            "first_seen": rows[0].timestamp if rows else None,
            "last_seen": rows[-1].timestamp if rows else None,
            "entries": [
                {
                    "timestamp": r.timestamp,
                    "camera_id": r.camera_id,
                    "location": r.location,
                    "status": r.status,
                    "memory_id": r.memory_id,
                }
                for r in rows
            ],
        }

    def get_last_seen(
        self, user_id: str, object_name: str, camera_id: str | None = None
    ) -> dict:
        key = object_key(object_name)
        row = self.history.last_seen(user_id, key)
        if row is None:
            return {
                "object": normalize_name(object_name),
                "found": False,
                "statement": f"{normalize_name(object_name)} has not been observed in memory yet.",
            }
        return {
            "object": normalize_name(object_name),
            "found": True,
            "last_seen": row.timestamp,
            "camera_id": row.camera_id,
            "location": row.location,
            "status": row.status,
            "statement": (
                f"{normalize_name(object_name)} was last observed at {row.location} "
                f"at {row.timestamp.isoformat()}."
            ),
        }

    # -------------------------------------------------------------- evidence
    def get_evidence(self, user_id: str, memory_id: str):
        rows = list(self.evidence.for_memory(user_id, memory_id))
        return rows
