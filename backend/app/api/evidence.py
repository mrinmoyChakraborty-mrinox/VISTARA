"""Evidence retrieval endpoint: authorized, user-scoped."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.app.core.security import CurrentUser, require_user
from backend.app.db.session import get_db
from backend.app.evidence.service import EvidenceService

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/{evidence_id}")
def get_evidence(
    evidence_id: str,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Return an authorized URL for the evidence frame (signed Supabase URL)."""
    service = EvidenceService()
    record = service.get_owned(user.id, evidence_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence not found")

    url = service.signed_url(record.storage_path)
    if url:
        return RedirectResponse(url=url)
    # Local/offline fallback: return metadata + path.
    return {
        "id": str(record.id),
        "memory_id": str(record.memory_id),
        "storage_path": record.storage_path,
        "mime_type": record.mime_type,
        "url": None,
    }
