"""Chat/tool-calling provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatTurn:
    """One model turn: either tool calls to execute, or a final answer."""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_message: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = ""


class ChatProvider(ABC):
    @abstractmethod
    def complete(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> ChatTurn:
        """Return a tool-calling turn or a final answer."""
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError
