"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { postChat } from "@/lib/apiClient";
import type { Evidence, ToolResult } from "@/types/domain";

export interface ChatTurn {
  id: string;
  question: string;
  answer: string;
  evidence: Evidence[];
  toolCalls: ToolResult[] | null;
  conversationId: string | null;
  status: "loading" | "done" | "error";
  error?: string;
}

interface ChatContextValue {
  turns: ChatTurn[];
  conversationId: string | null;
  sending: boolean;
  sendMessage: (message: string) => Promise<void>;
  clearChat: () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

function newId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const sendMessage = useCallback(
    async (message: string) => {
      const text = message.trim();
      if (!text || sending) return;
      setSending(true);
      const turnId = newId();
      setTurns((prev) => [
        ...prev,
        {
          id: turnId,
          question: text,
          answer: "",
          evidence: [],
          toolCalls: null,
          conversationId,
          status: "loading",
        },
      ]);
      try {
        const res = await postChat({
          conversation_id: conversationId ?? undefined,
          message: text,
        });
        setConversationId(res.conversation_id);
        // The answer is displayed verbatim; never rephrased by the UI.
        setTurns((prev) =>
          prev.map((turn) =>
            turn.id === turnId
              ? {
                  ...turn,
                  answer: res.answer,
                  evidence: res.evidence ?? [],
                  toolCalls: res.tool_calls ?? null,
                  conversationId: res.conversation_id,
                  status: "done",
                }
              : turn,
          ),
        );
      } catch (err) {
        const detail =
          err instanceof Error
            ? err.message
            : typeof err === "object" && err !== null && "message" in err
              ? String((err as { message: unknown }).message)
              : "The question could not be answered. Existing memories remain searchable.";
        setTurns((prev) =>
          prev.map((turn) =>
            turn.id === turnId
              ? { ...turn, status: "error", error: detail }
              : turn,
          ),
        );
      } finally {
        setSending(false);
      }
    },
    [conversationId, sending],
  );

  const clearChat = useCallback(() => {
    setTurns([]);
    setConversationId(null);
  }, []);

  const value = useMemo<ChatContextValue>(
    () => ({ turns, conversationId, sending, sendMessage, clearChat }),
    [turns, conversationId, sending, sendMessage, clearChat],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used inside ChatProvider");
  return ctx;
}
