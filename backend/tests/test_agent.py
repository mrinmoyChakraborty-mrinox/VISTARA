"""GPT-OSS agent tool execution + end-to-end mocked pipeline tests."""

from __future__ import annotations


from backend.app.agent.service import AgentService
from backend.app.agent.tools import ToolExecutor
from backend.app.db.session import session_scope
from backend.app.memory.schemas import VLMObject, VLMPerception, VLMScene
from backend.app.memory.service import MemoryService
from backend.app.perception.buffer import RollingBuffer
from backend.app.perception.gate import GateConfig, PerceptionGate
from backend.app.perception.pipeline import build_event_payload, frame_to_bgr
from backend.app.providers.mock import MockChatProvider, MockVisionProvider
from backend.tests.conftest import auth, create_camera, frame_bytes, make_frame


def _p(loc="center of desk"):
    return VLMPerception(
        scene=VLMScene(
            type="work desk", summary="desk", activity="work", environment="indoor"
        ),
        objects=[
            VLMObject(temporary_id="o", name="ESP32", location=loc, status="visible")
        ],
        events=[],
    )


def test_tool_executor_search_memory():
    # Uses the session-scoped DB; create a memory then execute the tool.
    from backend.tests.test_memory import _perception  # reuse helper

    cam = "00000000-0000-0000-0000-000000000001"
    with session_scope() as db:
        MemoryService(db).create_from_perception(
            "tool-user", cam, _perception("center of desk")
        )
    with session_scope() as db:
        executor = ToolExecutor(db, "tool-user")
        out = executor.execute("search_memory", {"query": "ESP32"})
        assert out["tool"] == "search_memory"
        assert isinstance(out["result"], list)
        # user isolation
        other = ToolExecutor(db, "someone-else").execute(
            "search_memory", {"query": "ESP32"}
        )
        assert other["result"] == []


def test_agent_loop_calls_tool_then_answers():
    cam = "00000000-0000-0000-0000-000000000002"
    with session_scope() as db:
        MemoryService(db).create_from_perception("chat-user", cam, _p("center of desk"))
    with session_scope() as db:
        provider = MockChatProvider(
            answer="The ESP32 was last observed in the center of the desk."
        )
        agent = AgentService(db, provider)
        result = agent.run("chat-user", "Where was the ESP32 before I moved it?")
        assert result["answer"].startswith("The ESP32")
        assert any(tc["tool"] == "search_memory" for tc in result["tool_calls"])
        assert result["conversation_id"]


def test_chat_endpoint(client):
    cam = create_camera(client, "Chat cam", user="user-a")
    with session_scope() as db:
        MemoryService(db).create_from_perception("user-a", cam, _p("center of desk"))
    res = client.post(
        "/api/chat", json={"message": "Where was my ESP32?"}, headers=auth("user-a")
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["answer"]
    assert body["conversation_id"]


def test_end_to_end_mocked_pipeline():
    """mock frames -> gate -> mock Qwen3.8 output -> memory -> retrieval -> mock GPT-OSS tool call -> answer."""
    cam = "00000000-0000-0000-0000-0000000000e2"
    # 1. gate fires on a real pixel change
    gate = PerceptionGate(
        GateConfig(change_threshold=0.005, persistence_frames=1, cooldown_seconds=0)
    )
    buffer = RollingBuffer(maxlen=10)
    buffer.push(frame_to_bgr(frame_bytes(0)), ts=0.0)
    gate.update(make_frame(0), now=0.0)
    decision = gate.update(make_frame(80), now=1.0)
    assert decision.fired
    buffer.push(frame_to_bgr(frame_bytes(80)), ts=1.0)

    # 2. build payload (main + context + crop)
    ctx = build_event_payload(buffer)
    assert ctx is not None and ctx.main_jpeg

    # 3. mock VLM output -> memory
    vision = MockVisionProvider(_p("beside laptop"))
    result = vision.analyze([ctx.main_jpeg])
    with session_scope() as db:
        mem_id, events = MemoryService(db).create_from_perception(
            "e2e-user", cam, result.perception
        )
        assert mem_id

    # 4. retrieval
    from backend.app.retrieval.service import RetrievalService

    with session_scope() as db:
        hits = RetrievalService(db).search_memory("e2e-user", query="ESP32")
        assert hits

    # 5. mock GPT-OSS tool call -> answer
    with session_scope() as db:
        agent = AgentService(db, MockChatProvider())
        out = agent.run("e2e-user", "Where was the ESP32?")
        assert out["answer"]
        assert out["tool_calls"]
