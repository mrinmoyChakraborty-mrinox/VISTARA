"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { RotateCcw, SendHorizontal, Sparkles } from "lucide-react";

import { useChat, type ChatTurn } from "@/components/providers/chat-provider";
import { EvidenceViewer } from "@/components/memory/evidence-viewer";
import { ToolCallList } from "@/components/chat/tool-call-list";
import { TypedText } from "@/components/ui-fx/typed-text";
import { TypingDots } from "@/components/ui-fx/typing-dots";
import type { Evidence } from "@/types/domain";

const SUGGESTED = [
  "Where did I last see my backpack?",
  "What changed in the last hour?",
  "Show me the ESP32",
];

function EvidenceStrip({
  evidence,
  onOpen,
}: {
  evidence: Evidence[];
  onOpen: (item: Evidence) => void;
}) {
  if (evidence.length === 0) return null;
  return (
    <div className="flex" style={{ gap: 8, marginTop: 8, flexWrap: "wrap" }}>
      {evidence.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onOpen(item)}
          aria-label={`Open evidence from ${item.timestamp}`}
          className="alist-item"
          style={{
            width: 72,
            height: 54,
            borderRadius: 10,
            border: "1px solid var(--line)",
            background: "linear-gradient(135deg, var(--desk), var(--soft))",
            cursor: "pointer",
            padding: 0,
            overflow: "hidden",
          }}
        />
      ))}
    </div>
  );
}

function Turn({ turn, onRetry }: { turn: ChatTurn; onRetry: () => void }) {
  const [viewing, setViewing] = useState<Evidence | null>(null);

  return (
    <div style={{ display: "grid", gap: 2 }}>
      <div className="msg q" style={{ animation: "pop .4s both" }}>
        {turn.question}
      </div>
      <div className="msg a" style={{ animation: "pop .4s both" }}>
        {turn.status === "loading" ? (
          <TypingDots label="Vistara is thinking" />
        ) : turn.status === "error" ? (
          <>
            <span role="alert">
              {turn.error ?? "The question could not be answered."}
            </span>
            <div style={{ marginTop: 8 }}>
              <button type="button" className="btn" onClick={onRetry}>
                <RotateCcw size={14} aria-hidden="true" />
                Retry
              </button>
            </div>
          </>
        ) : (
          <TypedText text={turn.answer} />
        )}
      </div>
      {turn.status === "done" && turn.toolCalls && turn.toolCalls.length > 0 && (
        <ToolCallList calls={turn.toolCalls} />
      )}
      {turn.status === "done" && (
        <EvidenceStrip evidence={turn.evidence} onOpen={setViewing} />
      )}
      <EvidenceViewer
        evidenceId={viewing?.id ?? null}
        directUrl={viewing?.url}
        cameraName={viewing?.camera_id}
        timestamp={viewing ? new Date(viewing.timestamp).toLocaleString() : undefined}
        description="Evidence frame for this answer"
        open={viewing !== null}
        onClose={() => setViewing(null)}
      />
    </div>
  );
}

function ChatBody() {
  const searchParams = useSearchParams();
  const { turns, sending, sendMessage, clearChat } = useChat();
  const [draft, setDraft] = useState("");
  const consumedPrefill = useRef(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !consumedPrefill.current && turns.length === 0) {
      consumedPrefill.current = true;
      setDraft(q);
    }
  }, [searchParams, turns.length]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [turns]);

  const send = (text: string) => {
    const message = text.trim();
    if (!message || sending) return;
    setDraft("");
    void sendMessage(message);
  };

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div className="flex flex-wrap items-end justify-between" style={{ gap: 12 }}>
        <div>
          <h2>Chat</h2>
          <p className="mute" style={{ marginTop: 8 }}>
            Plain words in, grounded answers out — always with the frame.
          </p>
        </div>
        {turns.length > 0 && (
          <button type="button" className="btn" onClick={clearChat}>
            New conversation
          </button>
        )}
      </div>

      <div className="panel" style={{ display: "grid", gap: 14, minHeight: 320 }}>
        {turns.length === 0 ? (
          <div style={{ display: "grid", gap: 12, alignContent: "center" }}>
            <p className="mute">
              <Sparkles size={15} aria-hidden="true" style={{ verticalAlign: -2 }} />{" "}
              Try one of these — answers come back with evidence attached.
            </p>
            <div className="chips" style={{ margin: 0 }}>
              {SUGGESTED.map((q) => (
                <button key={q} type="button" className="q" onClick={() => send(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          turns.map((turn) => (
            <Turn key={turn.id} turn={turn} onRetry={() => send(turn.question)} />
          ))
        )}
        <div ref={bottom} aria-hidden="true" />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(draft);
        }}
        style={{ display: "grid", gap: 10 }}
      >
        <div className="auth-field">
          <label htmlFor="chat-composer">Ask Vistara</label>
          <textarea
            id="chat-composer"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(draft);
              }
            }}
            placeholder="Where did I last see…"
            rows={3}
          />
        </div>
        <div>
          <button type="submit" className="btn shimmer" disabled={!draft.trim() || sending}>
            <SendHorizontal size={15} aria-hidden="true" />
            {sending ? "Thinking…" : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<p className="mute" role="status">Loading chat…</p>}>
      <ChatBody />
    </Suspense>
  );
}
