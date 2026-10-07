"""Groq GPT-OSS 20B chat provider (cloud-only). Tool calling via Groq."""

from __future__ import annotations

from backend.app.core.config import settings
from backend.app.providers.chat import ChatProvider, ChatTurn, ToolCall


class GroqGPTOSSProvider(ChatProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key if api_key is not None else settings.groq_api_key
        if not key:
            raise ValueError("GROQ_API_KEY is required for the Groq chat provider.")
        from groq import Groq

        self._client = Groq(api_key=key)
        self._model = model or settings.groq_chat_model
        self._timeout = settings.groq_timeout_seconds

    @property
    def model_name(self) -> str:
        return self._model

    def complete(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> ChatTurn:
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 800,
            "timeout": self._timeout,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        completion = self._client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        message = choice.message
        tool_calls: list[ToolCall] = []
        for tc in message.tool_calls or []:
            import json

            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        raw_message: dict = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            raw_message["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        return ChatTurn(
            content=message.content or "",
            tool_calls=tool_calls,
            raw_message=raw_message,
            finish_reason=choice.finish_reason or "",
        )
