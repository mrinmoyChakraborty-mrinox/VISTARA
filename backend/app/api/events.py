"""Event endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.security import CurrentUser, require_user
from backend.app.db.session import get_db
from backend.app.memory.schemas import MemoryEventOut
from backend.app.retrieval.service import RetrievalService

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=list[MemoryEventOut])
def list_events(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    event_type: str | None = None,
    object: str | None = None,
    camera_id: str | None = None,
    limit: int = 50,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    return RetrievalService(db).get_events(
        user.id,
        start_time=start_time,
        end_time=end_time,
        event_type=event_type,
        object_name=object,
        camera_id=camera_id,
        limit=limit,
    )
