"""Real Groq GPT-OSS 20B chat + agent tool loop. Skipped without GROQ_API_KEY."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.agent.service import AgentService
from backend.app.db.session import create_all, session_scope
from backend.app.memory.schemas import VLMObject, VLMPerception, VLMScene
from backend.app.memory.service import MemoryService, SceneState
from backend.app.providers.groq_gptoss import GroqGPTOSSProvider
from backend.tests.integration.conftest import requires_groq

pytestmark = [pytest.mark.integration, requires_groq]


def test_real_chat_simple():
    provider = GroqGPTOSSProvider()
    turn = provider.complete([{"role": "user", "content": "Reply with exactly: pong"}])
    assert "pong" in turn.content.lower()


def test_real_chat_tool_selection():
    from backend.app.agent.tools import TOOL_DEFINITIONS

    provider = GroqGPTOSSProvider()
    turn = provider.complete(
        [
            {
                "role": "system",
                "content": "You are the reasoning layer of a visual memory system.",
            },
            {"role": "user", "content": "Where was my ESP32 before I moved it?"},
        ],
        tools=TOOL_DEFINITIONS,
    )
    assert turn.tool_calls, "model should call a memory tool"
    assert turn.tool_calls[0].name in {
        "search_memory",
        "get_object_history",
        "get_last_seen",
        "get_events",
        "get_scene",
        "get_memory",
        "get_evidence",
    }


def test_real_agent_loop_grounded_in_db(tmp_path, monkeypatch):
    # Use a local SQLite DB so the tool executes against real rows, real Groq for reasoning.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'agent.db'}")
    import backend.app.db.session as sess

    sess._engine = None
    sess._SessionLocal = None
    engine = sess.get_engine()
    create_all(engine)

    user = "11111111-1111-1111-1111-111111111111"
    cam = "22222222-2222-2222-2222-222222222222"
    ts = datetime.now(timezone.utc)

    def perception(loc: str) -> VLMPerception:
        return VLMPerception(
            scene=VLMScene(
                type="work desk", summary="desk", activity="work", environment="indoor"
            ),
            objects=[
                VLMObject(
                    temporary_id="o", name="ESP32", location=loc, status="visible"
                )
            ],
            events=[],
        )

    with session_scope() as db:
        svc = MemoryService(db)
        svc.create_from_perception(
            user, cam, perception("center of desk"), timestamp=ts
        )
        svc.create_from_perception(
            user,
            cam,
            perception("beside laptop"),
            previous_state=SceneState(locations={"ESP32": "center of desk"}),
            timestamp=ts,
        )

    with session_scope() as db:
        agent = AgentService(db, GroqGPTOSSProvider())
        result = agent.run(user, "Where was the ESP32 before I moved it?")
    assert result["answer"]
    assert any(
        t["tool"]
        in ("search_memory", "get_object_history", "get_last_seen", "get_events")
        for t in result["tool_calls"]
    )
