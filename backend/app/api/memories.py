"""Memory endpoints (list, detail, embedding update)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.logging import log_event
from backend.app.core.security import CurrentUser, require_user
from backend.app.db.repositories import MemoryRepository
from backend.app.db.session import get_db
from backend.app.memory.schemas import EmbeddingIn, MemoryOut
from backend.app.memory.serialize import memory_to_out

router = APIRouter(prefix="/api/memories", tags=["memories"])


@router.get("", response_model=list[MemoryOut])
def list_memories(
    camera_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 50,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    rows = MemoryRepository(db).list(
        user.id, camera_id=camera_id, start=start, end=end, limit=limit
    )
    return [memory_to_out(m) for m in rows]


@router.get("/{memory_id}", response_model=MemoryOut)
def get_memory(
    memory_id: str,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    memory = MemoryRepository(db).get(user.id, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory_to_out(memory)


@router.post("/{memory_id}/embedding", response_model=MemoryOut)
def set_embedding(
    memory_id: str,
    body: EmbeddingIn,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Client-side embedding upload. 1024-dim, current user only, validated."""
    if len(body.embedding) != 1024:
        raise HTTPException(
            status_code=422, detail="Embedding must be exactly 1024 dimensions."
        )
    memory = MemoryRepository(db).set_embedding(user.id, memory_id, body.embedding)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    db.commit()
    log_event("embedding_updated", status="ok", user_id=user.id, memory_id=memory_id)
    return memory_to_out(memory)
