"""Repositories: the ONLY place SQL is executed.

Hard rule: every read/write of user-owned data takes an explicit user_id that
comes from the authenticated identity. No repository method accepts a user_id
that could originate from client input.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Camera,
    CameraSession,
    ChatConversation,
    ChatMessage,
    Evidence,
    Memory,
    MemoryEvent,
    MemoryObject,
    ObjectHistory,
    Profile,
)


def _as_uuid(value: str | uuid.UUID) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        # Non-UUID identities (mock/demo users) map to a stable UUIDv5 so the
        # UUID-typed columns work without weakening real Supabase auth.
        return uuid.uuid5(uuid.NAMESPACE_URL, f"visual-memory:{value}")


def _json_safe(value):
    """Recursively convert UUIDs/datetimes/sets to JSON-serializable forms."""
    import datetime

    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return [_json_safe(v) for v in sorted(value, key=repr)]
    return value


class ProfileRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: str) -> Profile | None:
        return self.db.get(Profile, _as_uuid(user_id))

    def upsert(self, user_id: str, display_name: str | None) -> Profile:
        profile = self.get(user_id)
        if profile is None:
            profile = Profile(id=_as_uuid(user_id), display_name=display_name)
            self.db.add(profile)
        else:
            profile.display_name = display_name
        self.db.flush()
        return profile


class CameraRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, user_id: str) -> Sequence[Camera]:
        return self.db.scalars(
            select(Camera)
            .where(Camera.user_id == _as_uuid(user_id))
            .order_by(Camera.created_at)
        ).all()

    def get(self, user_id: str, camera_id: str) -> Camera | None:
        return self.db.scalars(
            select(Camera).where(
                Camera.id == _as_uuid(camera_id), Camera.user_id == _as_uuid(user_id)
            )
        ).first()

    def create(
        self, user_id: str, name: str, source_type: str, config: dict | None = None
    ) -> Camera:
        camera = Camera(
            user_id=_as_uuid(user_id),
            name=name,
            source_type=source_type,
            config=config or {},
            status="idle",
        )
        self.db.add(camera)
        self.db.flush()
        return camera

    def update_status(self, user_id: str, camera_id: str, status: str) -> Camera | None:
        camera = self.get(user_id, camera_id)
        if camera is None:
            return None
        camera.status = status
        camera.last_seen_at = datetime.now(timezone.utc)
        self.db.flush()
        return camera

    def delete(self, user_id: str, camera_id: str) -> bool:
        camera = self.get(user_id, camera_id)
        if camera is None:
            return False
        self.db.delete(camera)
        self.db.flush()
        return True


class CameraSessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def start(self, user_id: str, camera_id: str) -> CameraSession:
        session = CameraSession(
            user_id=_as_uuid(user_id), camera_id=_as_uuid(camera_id), status="started"
        )
        self.db.add(session)
        self.db.flush()
        return session

    def stop(self, user_id: str, camera_id: str) -> CameraSession | None:
        session = self.db.scalars(
            select(CameraSession)
            .where(
                CameraSession.user_id == _as_uuid(user_id),
                CameraSession.camera_id == _as_uuid(camera_id),
                CameraSession.status == "started",
            )
            .order_by(CameraSession.started_at.desc())
        ).first()
        if session is None:
            return None
        session.status = "stopped"
        session.ended_at = datetime.now(timezone.utc)
        self.db.flush()
        return session

    def latest(self, user_id: str, camera_id: str) -> CameraSession | None:
        return self.db.scalars(
            select(CameraSession)
            .where(
                CameraSession.user_id == _as_uuid(user_id),
                CameraSession.camera_id == _as_uuid(camera_id),
            )
            .order_by(CameraSession.started_at.desc())
        ).first()


class MemoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: str,
        camera_id: str,
        timestamp: datetime,
        scene_type: str,
        scene_summary: str,
        activity: str,
        environment: str,
        confidence: float,
        is_baseline: bool = False,
    ) -> Memory:
        memory = Memory(
            user_id=_as_uuid(user_id),
            camera_id=_as_uuid(camera_id),
            timestamp=timestamp,
            scene_type=scene_type,
            scene_summary=scene_summary,
            activity=activity,
            environment=environment,
            confidence=confidence,
            is_baseline=is_baseline,
        )
        self.db.add(memory)
        self.db.flush()
        return memory

    def get(self, user_id: str, memory_id: str) -> Memory | None:
        return self.db.scalars(
            select(Memory).where(
                Memory.id == _as_uuid(memory_id), Memory.user_id == _as_uuid(user_id)
            )
        ).first()

    def list(
        self,
        user_id: str,
        camera_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 50,
    ) -> Sequence[Memory]:
        stmt = select(Memory).where(Memory.user_id == _as_uuid(user_id))
        if camera_id:
            stmt = stmt.where(Memory.camera_id == _as_uuid(camera_id))
        if start:
            stmt = stmt.where(Memory.timestamp >= start)
        if end:
            stmt = stmt.where(Memory.timestamp <= end)
        stmt = stmt.order_by(Memory.timestamp.desc()).limit(limit)
        return self.db.scalars(stmt).all()

    def latest(self, user_id: str, camera_id: str | None = None) -> Memory | None:
        rows = self.list(user_id, camera_id=camera_id, limit=1)
        return rows[0] if rows else None

    def set_embedding(
        self, user_id: str, memory_id: str, vector: list[float]
    ) -> Memory | None:
        memory = self.get(user_id, memory_id)
        if memory is None:
            return None
        memory.embedding = vector
        self.db.flush()
        return memory

    def set_evidence(
        self, user_id: str, memory_id: str, evidence_id: str
    ) -> Memory | None:
        memory = self.get(user_id, memory_id)
        if memory is None:
            return None
        memory.evidence_id = _as_uuid(evidence_id)
        self.db.flush()
        return memory


class MemoryObjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        user_id: str,
        memory_id: str,
        name: str,
        normalized_name: str,
        location: str,
        status: str,
        attributes: dict | None = None,
    ) -> MemoryObject:
        obj = MemoryObject(
            user_id=_as_uuid(user_id),
            memory_id=_as_uuid(memory_id),
            name=name,
            normalized_name=normalized_name,
            location=location,
            status=status,
            attributes=attributes or {},
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def list_for_memory(self, user_id: str, memory_id: str) -> Sequence[MemoryObject]:
        return self.db.scalars(
            select(MemoryObject).where(
                MemoryObject.user_id == _as_uuid(user_id),
                MemoryObject.memory_id == _as_uuid(memory_id),
            )
        ).all()


class MemoryEventRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        user_id: str,
        memory_id: str,
        camera_id: str,
        timestamp: datetime,
        event_type: str,
        object_name: str,
        from_location: str,
        to_location: str,
        description: str,
        confidence: float,
    ) -> MemoryEvent:
        event = MemoryEvent(
            user_id=_as_uuid(user_id),
            memory_id=_as_uuid(memory_id),
            camera_id=_as_uuid(camera_id),
            timestamp=timestamp,
            event_type=event_type,
            object_name=object_name,
            from_location=from_location,
            to_location=to_location,
            description=description,
            confidence=confidence,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def list(
        self,
        user_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
        event_type: str | None = None,
        object_name: str | None = None,
        camera_id: str | None = None,
        limit: int = 100,
    ) -> Sequence[MemoryEvent]:
        stmt = select(MemoryEvent).where(MemoryEvent.user_id == _as_uuid(user_id))
        if start:
            stmt = stmt.where(MemoryEvent.timestamp >= start)
        if end:
            stmt = stmt.where(MemoryEvent.timestamp <= end)
        if event_type:
            stmt = stmt.where(MemoryEvent.event_type == event_type)
        if object_name:
            stmt = stmt.where(MemoryEvent.object_name == object_name)
        if camera_id:
            stmt = stmt.where(MemoryEvent.camera_id == _as_uuid(camera_id))
        stmt = stmt.order_by(MemoryEvent.timestamp.desc()).limit(limit)
        return self.db.scalars(stmt).all()

    def list_for_memory(self, user_id: str, memory_id: str) -> Sequence[MemoryEvent]:
        return self.db.scalars(
            select(MemoryEvent).where(
                MemoryEvent.user_id == _as_uuid(user_id),
                MemoryEvent.memory_id == _as_uuid(memory_id),
            )
        ).all()


class ObjectHistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        user_id: str,
        object_key: str,
        camera_id: str,
        memory_id: str,
        timestamp: datetime,
        location: str,
        status: str,
    ) -> ObjectHistory:
        row = ObjectHistory(
            user_id=_as_uuid(user_id),
            object_key=object_key,
            camera_id=_as_uuid(camera_id),
            memory_id=_as_uuid(memory_id),
            timestamp=timestamp,
            location=location,
            status=status,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def list(
        self, user_id: str, object_key: str, limit: int = 200
    ) -> Sequence[ObjectHistory]:
        return self.db.scalars(
            select(ObjectHistory)
            .where(
                ObjectHistory.user_id == _as_uuid(user_id),
                ObjectHistory.object_key == object_key,
            )
            .order_by(ObjectHistory.timestamp.asc())
            .limit(limit)
        ).all()

    def last_seen(self, user_id: str, object_key: str) -> ObjectHistory | None:
        return self.db.scalars(
            select(ObjectHistory)
            .where(
                ObjectHistory.user_id == _as_uuid(user_id),
                ObjectHistory.object_key == object_key,
            )
            .order_by(ObjectHistory.timestamp.desc())
        ).first()


class EvidenceRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        user_id: str,
        camera_id: str,
        memory_id: str,
        timestamp: datetime,
        storage_path: str,
        mime_type: str = "image/jpeg",
    ) -> Evidence:
        evidence = Evidence(
            user_id=_as_uuid(user_id),
            camera_id=_as_uuid(camera_id),
            memory_id=_as_uuid(memory_id),
            timestamp=timestamp,
            storage_path=storage_path,
            mime_type=mime_type,
        )
        self.db.add(evidence)
        self.db.flush()
        return evidence

    def get(self, user_id: str, evidence_id: str) -> Evidence | None:
        return self.db.scalars(
            select(Evidence).where(
                Evidence.id == _as_uuid(evidence_id),
                Evidence.user_id == _as_uuid(user_id),
            )
        ).first()

    def for_memory(self, user_id: str, memory_id: str) -> Sequence[Evidence]:
        return self.db.scalars(
            select(Evidence).where(
                Evidence.user_id == _as_uuid(user_id),
                Evidence.memory_id == _as_uuid(memory_id),
            )
        ).all()


class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_conversation(
        self, user_id: str, conversation_id: str
    ) -> ChatConversation | None:
        return self.db.scalars(
            select(ChatConversation).where(
                ChatConversation.id == _as_uuid(conversation_id),
                ChatConversation.user_id == _as_uuid(user_id),
            )
        ).first()

    def create_conversation(
        self, user_id: str, title: str = "New conversation"
    ) -> ChatConversation:
        convo = ChatConversation(user_id=_as_uuid(user_id), title=title)
        self.db.add(convo)
        self.db.flush()
        return convo

    def add_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            user_id=_as_uuid(user_id),
            conversation_id=_as_uuid(conversation_id),
            role=role,
            content=content,
            # Tool results embed ORM-derived dicts (UUIDs, datetimes) that no
            # JSON column accepts. Normalize once at the persistence boundary
            # so chat history can never 500 on SQLite or Postgres JSON.
            tool_calls=_json_safe(tool_calls),
        )
        self.db.add(message)
        self.db.flush()
        return message

    def messages(
        self, user_id: str, conversation_id: str, limit: int = 100
    ) -> Sequence[ChatMessage]:
        return self.db.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.user_id == _as_uuid(user_id),
                ChatMessage.conversation_id == _as_uuid(conversation_id),
            )
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        ).all()
