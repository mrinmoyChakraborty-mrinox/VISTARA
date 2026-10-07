"""Object history endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.security import CurrentUser, require_user
from backend.app.db.session import get_db
from backend.app.retrieval.service import RetrievalService

router = APIRouter(prefix="/api/objects", tags=["objects"])


@router.get("/{name}/history")
def object_history(
    name: str, user: CurrentUser = Depends(require_user), db: Session = Depends(get_db)
):
    return RetrievalService(db).get_object_history(user.id, name)
