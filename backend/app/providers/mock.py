"""Deterministic offline providers for tests (no Groq, no network, no GPU)."""

from __future__ import annotations

from backend.app.memory.schemas import (
    VLMObject,
    VLMPerception,
    VLMScene,
    VLMEvent,
)
from backend.app.providers.chat import ChatProvider, ChatTurn, ToolCall
from backend.app.providers.vision import VisionProvider, VisionResult


class MockVisionProvider(VisionProvider):
    """Returns a fixed perception. Optional per-call override via `next_perception`."""

    def __init__(self, perception: VLMPerception | None = None):
        self._perception = perception or default_perception()
        self.next_perception: VLMPerception | None = None

    @property
    def model_name(self) -> str:
        return "mock-vlm"

    def analyze(
        self, frames: list[bytes], previous_state: dict | None = None
    ) -> VisionResult:
        perception = self.next_perception or self._perception
        return VisionResult(
            perception=perception,
            model="mock-vlm",
            latency_ms=1.0,
            payload_bytes=sum(len(f) for f in frames),
        )


def default_perception() -> VLMPerception:
    return VLMPerception(
        scene=VLMScene(
            type="work desk",
            summary="A desk with a laptop, an ESP32 board, a phone, a notebook and a bottle.",
            activity="electronics work",
            environment="indoor workspace",
        ),
        objects=[
            VLMObject(
                temporary_id="obj_01",
                name="ESP32",
                location="center of desk",
                status="visible",
            ),
            VLMObject(
                temporary_id="obj_02",
                name="phone",
                location="left of laptop",
                status="visible",
            ),
            VLMObject(
                temporary_id="obj_03",
                name="notebook",
                location="right side",
                status="visible",
            ),
            VLMObject(
                temporary_id="obj_04",
                name="bottle",
                location="top right",
                status="visible",
            ),
        ],
        events=[
            VLMEvent(
                type="object_moved",
                object_name="ESP32",
                from_location="center of desk",
                to_location="beside laptop",
                description="The ESP32 moved from the center of the desk to beside the laptop.",
                confidence=0.9,
            )
        ],
    )


class MockChatProvider(ChatProvider):
    """Scripted chat provider.

    By default it issues one search_memory tool call on the first turn, then
    produces a final answer. Tests can script exact turns via `script`.
    """

    def __init__(self, script: list[ChatTurn] | None = None, answer: str | None = None):
        self._script = script or []
        self._answer = answer or "It was last observed in the center of the desk."
        self.calls: list[list[dict]] = []

    @property
    def model_name(self) -> str:
        return "mock-chat"

    def complete(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> ChatTurn:
        self.calls.append(messages)
        if self._script:
            return self._script.pop(0)
        # If a tool result is present, we're on the final turn.
        if any(m.get("role") == "tool" for m in messages):
            return ChatTurn(content=self._answer, finish_reason="stop")
        return ChatTurn(
            content="",
            tool_calls=[
                ToolCall(
                    id="call_1", name="search_memory", arguments={"query": "ESP32"}
                )
            ],
            raw_message={
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "search_memory",
                            "arguments": '{"query": "ESP32"}',
                        },
                    }
                ],
            },
            finish_reason="tool_calls",
        )
