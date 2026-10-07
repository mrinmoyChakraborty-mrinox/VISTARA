"""Shared FastAPI dependencies: DB session, current user, provider factories.

Provider selection is centralized here so routes never touch Groq directly and
tests can swap in mock providers.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.core.config import settings

# Providers are injectable for tests.
_vision_provider_override = None
_chat_provider_override = None
_agent_override = None


def get_db_dep():
    from backend.app.db.session import get_db

    yield from get_db()


def get_vision_provider():
    if _vision_provider_override is not None:
        return _vision_provider_override
    if settings.mock_mode:
        from backend.app.providers.mock import MockVisionProvider

        return MockVisionProvider()
    from backend.app.providers.groq_qwen38 import GroqQwen38VisionProvider

    return GroqQwen38VisionProvider()


def get_chat_provider():
    if _chat_provider_override is not None:
        return _chat_provider_override
    if settings.mock_mode:
        from backend.app.providers.mock import MockChatProvider

        return MockChatProvider()
    from backend.app.providers.groq_gptoss import GroqGPTOSSProvider

    return GroqGPTOSSProvider()


def set_vision_provider(provider) -> None:
    global _vision_provider_override
    _vision_provider_override = provider


def set_chat_provider(provider) -> None:
    global _chat_provider_override
    _chat_provider_override = provider


def get_agent_service(db: Session):
    from backend.app.agent.service import AgentService

    return AgentService(db, get_chat_provider())
