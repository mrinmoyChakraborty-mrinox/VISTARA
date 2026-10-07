"""EvidenceService: store event-frame JPEGs and issue authorized retrieval.

Primary store is Supabase Storage (private bucket); authorized access via signed
URLs. Falls back to a local directory when Supabase is not configured, which keeps
tests and offline dev working with no cloud dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from backend.app.core.config import settings
from backend.app.core.logging import log_event
from backend.app.db.repositories import EvidenceRepository
from backend.app.db.session import session_scope


def local_evidence_dir() -> Path:
    # Legacy EVIDENCE_DIR is honored when LOCAL_EVIDENCE_DIR is unset.
    import os

    if not settings.local_evidence_dir.strip():
        legacy = os.getenv("EVIDENCE_DIR", "").strip()
        if legacy:
            return Path(legacy)
    return Path(settings.local_evidence_dir or "./data/evidence")


@dataclass
class StoredEvidence:
    evidence_id: str
    memory_id: str
    storage_path: str
    mime_type: str
    url: str | None


class EvidenceService:
    def __init__(self, db=None):
        self._db = db
        self._client = None

    # ------------------------------------------------------------- storage
    def _supabase(self):
        if self._client is not None:
            return self._client
        if not (settings.supabase_url and settings.supabase_service_role_key):
            return None
        from supabase import create_client

        self._client = create_client(
            settings.supabase_url, settings.supabase_service_role_key
        )
        return self._client

    def _build_path(
        self, user_id: str, camera_id: str, memory_id: str, ts: datetime
    ) -> str:
        day = ts.strftime("%Y-%m-%d")
        return f"{user_id}/{camera_id}/{day}/mem_{memory_id}.jpg"

    def store_frame(
        self,
        user_id: str,
        camera_id: str,
        memory_id: str,
        jpeg: bytes,
        timestamp: datetime,
    ) -> StoredEvidence:
        path = self._build_path(user_id, camera_id, memory_id, timestamp)
        client = self._supabase()
        if client is not None:
            client.storage.from_(settings.supabase_evidence_bucket).upload(
                path,
                jpeg,
                {"content-type": "image/jpeg", "upsert": "true"},
            )
        else:
            local = local_evidence_dir() / path
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(jpeg)
        log_event(
            "evidence_stored", status="ok", memory_id=memory_id, extra={"path": path}
        )
        return StoredEvidence(
            evidence_id="",
            memory_id=memory_id,
            storage_path=path,
            mime_type="image/jpeg",
            url=None,
        )

    def signed_url(self, storage_path: str, expires_in: int = 3600) -> str | None:
        client = self._supabase()
        if client is None:
            return None
        res = client.storage.from_(settings.supabase_evidence_bucket).create_signed_url(
            storage_path, expires_in
        )
        return res.get("signedURL") or res.get("signedUrl")

    # -------------------------------------------------------------- records
    def create_record(
        self,
        db,
        user_id,
        camera_id,
        memory_id,
        timestamp,
        storage_path,
        mime_type="image/jpeg",
    ):
        return EvidenceRepository(db).add(
            user_id=user_id,
            camera_id=camera_id,
            memory_id=memory_id,
            timestamp=timestamp,
            storage_path=storage_path,
            mime_type=mime_type,
        )

    def get_owned(self, user_id: str, evidence_id: str):
        with session_scope() as db:
            record = EvidenceRepository(db).get(user_id, evidence_id)
            if record is None:
                return None
            db.expunge(record)
            return record

    def get_owned_url(self, user_id: str, evidence_id: str) -> str | None:
        record = self.get_owned(user_id, evidence_id)
        if record is None:
            return None
        return self.signed_url(record.storage_path)

    def persist_frame_and_record(
        self,
        db,
        user_id: str,
        camera_id: str,
        memory_id: str,
        jpeg: bytes,
        timestamp: datetime,
    ):
        stored = self.store_frame(user_id, camera_id, memory_id, jpeg, timestamp)
        record = self.create_record(
            db,
            user_id,
            camera_id,
            memory_id,
            timestamp,
            stored.storage_path,
            stored.mime_type,
        )
        return record
