"""AgentService: GPT-OSS tool-calling loop over the memory service layer."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from backend.app.agent.prompts import SYSTEM_PROMPT
from backend.app.agent.tools import TOOL_DEFINITIONS, ToolExecutor
from backend.app.core.logging import log_event
from backend.app.db.repositories import ChatRepository
from backend.app.providers.chat import ChatProvider, ChatTurn

MAX_TOOL_ITERATIONS = 4


class AgentService:
    def __init__(self, db: Session, provider: ChatProvider):
        self.db = db
        self.provider = provider
        self.chats = ChatRepository(db)

    def run(
        self,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
        query_vector: list[float] | None = None,
    ) -> dict:
        log_event("chat_started", status="ok", user_id=user_id)

        conversation = None
        if conversation_id:
            conversation = self.chats.get_conversation(user_id, conversation_id)
        if conversation is None:
            conversation = self.chats.create_conversation(user_id, title=message[:60])

        self.chats.add_message(user_id, str(conversation.id), "user", message)

        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for prior in self.chats.messages(user_id, str(conversation.id)):
            if prior.role in ("user", "assistant") and prior.content:
                messages.append({"role": prior.role, "content": prior.content})

        executor = ToolExecutor(self.db, user_id, query_vector=query_vector)
        tool_results: list[dict] = []
        answer = ""

        for _ in range(MAX_TOOL_ITERATIONS):
            turn: ChatTurn = self.provider.complete(messages, tools=TOOL_DEFINITIONS)
            if not turn.tool_calls:
                answer = turn.content or ""
                break

            messages.append(turn.raw_message)
            for call in turn.tool_calls:
                result = executor.execute(call.name, call.arguments)
                tool_results.append(
                    {
                        "tool": call.name,
                        "args": call.arguments,
                        "result": result.get("result"),
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, default=str),
                    }
                )
        else:
            answer = "I gathered memory data but could not finish reasoning in time. Please retry."

        if not answer and tool_results:
            answer = "Here is what I found in your visual memory."

        self.chats.add_message(
            user_id,
            str(conversation.id),
            "assistant",
            answer,
            tool_calls=tool_results or None,
        )
        self.db.flush()

        evidence = self._collect_evidence(user_id, tool_results)
        log_event(
            "chat_completed",
            status="ok",
            user_id=user_id,
            extra={"tool_calls": len(tool_results)},
        )

        return {
            "conversation_id": str(conversation.id),
            "answer": answer,
            "evidence": evidence,
            "tool_calls": tool_results,
        }

    @staticmethod
    def _collect_evidence(user_id: str, tool_results: list[dict]) -> list[dict]:
        memory_ids: list[str] = []
        for entry in tool_results:
            result = entry.get("result")
            if isinstance(result, dict):
                if result.get("id") and result.get("scene"):
                    memory_ids.append(result["id"])
                for ev in result.get("events", []) or []:
                    if isinstance(ev, dict) and ev.get("memory_id"):
                        memory_ids.append(ev["memory_id"])
        if not memory_ids:
            return []

        from backend.app.db.session import session_scope
        from backend.app.evidence.service import EvidenceService
        from backend.app.memory.serialize import evidence_to_out
        from backend.app.db.repositories import EvidenceRepository

        out: list[dict] = []
        service = EvidenceService()
        with session_scope() as db:
            repo = EvidenceRepository(db)
            for memory_id in dict.fromkeys(memory_ids):
                for record in repo.for_memory(user_id, memory_id):
                    url = service.signed_url(record.storage_path)
                    out.append(evidence_to_out(record, url=url).model_dump(mode="json"))
        return out
