"""Evidence retrieval endpoint: authorized, user-scoped."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from backend.app.core.security import CurrentUser, require_user
from backend.app.db.session import get_db
from backend.app.evidence.service import EvidenceService, local_evidence_dir

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/{evidence_id}")
def get_evidence(
    evidence_id: str,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Return the evidence frame: signed Supabase URL redirect when cloud
    storage is configured, local file bytes otherwise (local demo mode)."""
    service = EvidenceService()
    record = service.get_owned(user.id, evidence_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence not found")

    url = service.signed_url(record.storage_path)
    if url:
        return RedirectResponse(url=url)
    # Local/offline: serve the stored JPEG directly (same auth + ownership).
    local = local_evidence_dir() / record.storage_path
    if local.is_file():
        return FileResponse(path=local, media_type=record.mime_type or "image/jpeg")
    # Metadata fallback when the file itself is gone.
    return {
        "id": str(record.id),
        "memory_id": str(record.memory_id),
        "storage_path": record.storage_path,
        "mime_type": record.mime_type,
        "url": None,
    }
