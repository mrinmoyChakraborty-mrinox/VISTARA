"""Chat endpoint: POST /api/chat -> GPT-OSS tool loop over visual memory."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.deps import get_agent_service
from backend.app.core.security import CurrentUser, require_user
from backend.app.db.session import get_db

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatIn(BaseModel):
    message: str
    conversation_id: str | None = None
    query_vector: list[float] | None = None


@router.post("")
def chat(
    body: ChatIn,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    agent = get_agent_service(db)
    result = agent.run(
        user.id,
        body.message,
        conversation_id=body.conversation_id,
        query_vector=body.query_vector,
    )
    db.commit()
    return result
