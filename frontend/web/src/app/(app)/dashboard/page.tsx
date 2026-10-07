"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";
import { ArrowRight, Camera as CameraIcon, History, MessagesSquare } from "lucide-react";

import { useCamera } from "@/components/providers/camera-provider";
import { AnimatedList } from "@/components/ui-fx/animated-list";
import { NumberTicker } from "@/components/ui-fx/number-ticker";
import { StatusPill } from "@/components/ui-fx/status-pill";
import { useCamerasQuery, useMemoriesQuery } from "@/hooks/use-cameras";
import { useEventsQuery } from "@/hooks/use-memory";
import { isEnvConfigured, missingEnvVars } from "@/lib/env";
import type { CameraStatus } from "@/types/domain";

const STATUS_ORDER: CameraStatus[] = ["active", "idle", "disconnected", "error"];

function PanelError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" style={{ display: "grid", gap: 8, justifyItems: "start" }}>
      <b>Could not load this panel.</b>
      <p className="mono mute">{message}</p>
      <button type="button" className="btn" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}

function PanelSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="grid" style={{ gap: 8 }} role="status" aria-label="Loading panel">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skel" style={{ height: 64, borderRadius: 14 }} />
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { processing, sessionMemories, lastMemory } = useCamera();
  const cameras = useCamerasQuery();
  const memories = useMemoriesQuery();
  const events = useEventsQuery();
  const [question, setQuestion] = useState("");
  // Disabled queries stay pending forever — say so instead of shimmering.
  const envReady = isEnvConfigured();
  const envMissing = missingEnvVars();

  const counts = useMemo(() => {
    const base: Record<CameraStatus, number> = {
      active: 0,
      idle: 0,
      disconnected: 0,
      error: 0,
    };
    for (const camera of cameras.data ?? []) {
      // The backend may report statuses outside the known set; ignore those
      // instead of producing NaN counts.
      if (camera.status in base) base[camera.status] += 1;
    }
    return base;
  }, [cameras.data]);

  const cameraNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const camera of cameras.data ?? []) map[camera.id] = camera.name;
    return map;
  }, [cameras.data]);

  const recentMemories = useMemo(() => {
    const seen = new Set(sessionMemories.map((m) => m.id));
    const stored = (memories.data ?? []).filter((m) => !seen.has(m.id));
    return [...sessionMemories, ...stored]
      .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
      .slice(0, 5);
  }, [sessionMemories, memories.data]);

  const recentEvents = useMemo(() => {
    const sessionEvents = sessionMemories.flatMap((m) => m.events ?? []);
    const seen = new Set(sessionEvents.map((e) => e.id));
    const stored = (events.data ?? []).filter((e) => !seen.has(e.id));
    return [...sessionEvents, ...stored]
      .sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1))
      .slice(0, 5);
  }, [sessionMemories, events.data]);

  const pillState: 0 | 1 | 2 =
    processing === "analyzing" ? 1 : sessionMemories.length > 0 ? 2 : 0;

  const ask = (e: FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    router.push(`/chat?q=${encodeURIComponent(q)}`);
  };

  return (
    <div style={{ display: "grid", gap: 24 }}>
      <div>
        <h2>Dashboard</h2>
        <p className="mute" style={{ marginTop: 8 }}>
          Cameras, fresh memories, and the loop status at a glance.
        </p>
      </div>

      {!envReady && (
        <div role="alert" className="panel" style={{ display: "grid", gap: 10, justifyItems: "start" }}>
          <b>Backend is not configured.</b>
          <p className="mono mute" style={{ fontSize: ".85rem" }}>
            Missing: {envMissing.join(", ")}. Copy frontend/web/.env.example to
            .env.local (local demo needs only the backend URLs) and restart the
            dev server.
          </p>
        </div>
      )}

      <div className="panel">
        <div style={{ border: 0, boxShadow: "none", background: "transparent" }}>
          <div
            className="flex flex-wrap items-center justify-between"
            style={{ gap: 12, marginBottom: 16 }}
          >
            <b className="mono mute">CAMERA SUMMARY</b>
            <StatusPill state={pillState} style={{ margin: 0 }} />
          </div>
          {cameras.isPending ? (
            <PanelSkeleton rows={2} />
          ) : cameras.isError ? (
            <PanelError
              message="Camera counts are unavailable."
              onRetry={() => cameras.refetch()}
            />
          ) : (cameras.data ?? []).length === 0 ? (
            <div style={{ display: "grid", gap: 10, justifyItems: "start" }}>
              <CameraIcon size={22} aria-hidden="true" style={{ color: "var(--mute)" }} />
              <b>No cameras yet.</b>
              <a className="btn shimmer" href="/cameras">
                Add camera
              </a>
            </div>
          ) : (
            <div
              style={{
                display: "grid",
                gap: 12,
                gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
              }}
            >
              {STATUS_ORDER.map((status) => (
                <div key={status} style={{ textAlign: "center" }}>
                  <span
                    style={{
                      display: "block",
                      fontFamily: "var(--font-d)",
                      fontSize: "2rem",
                      color: "var(--acc)",
                    }}
                  >
                    <NumberTicker value={counts[status]} />
                  </span>
                  <span className="mono mute">{status}</span>
                </div>
              ))}
            </div>
          )}
          <p className="mono mute" style={{ marginTop: 12 }}>
            {processing === "analyzing" ? "● analyzing" : "○ idle"}
            {lastMemory ? ` · last memory ${lastMemory.id.slice(0, 8)}` : ""}
          </p>
        </div>
      </div>

      <div className="panel">
        <b className="mono mute">QUICK ASK</b>
        <form onSubmit={ask} className="flex flex-wrap" style={{ gap: 10, marginTop: 12 }}>
          <div className="auth-field" style={{ flex: "1 1 240px" }}>
            <label htmlFor="dashboard-ask" className="mono mute">
              Ask about your memories
            </label>
            <input
              id="dashboard-ask"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Where did I last see my backpack?"
            />
          </div>
          <button type="submit" className="btn shimmer" disabled={!question.trim()}>
            Ask in chat
            <ArrowRight size={15} aria-hidden="true" />
          </button>
        </form>
      </div>

      <div className="pv-grid" style={{ marginTop: 0 }}>
        <div className="panel" style={{ display: "grid", gap: 12, alignContent: "start" }}>
          <div className="flex items-center justify-between" style={{ gap: 12 }}>
            <b className="mono mute">RECENT MEMORIES</b>
            <History size={16} aria-hidden="true" style={{ color: "var(--mute)" }} />
          </div>
          {memories.isPending ? (
            <PanelSkeleton rows={3} />
          ) : memories.isError ? (
            <PanelError message="Memories are unavailable." onRetry={() => memories.refetch()} />
          ) : recentMemories.length === 0 ? (
            <div style={{ display: "grid", gap: 10, justifyItems: "start" }}>
              <b>No memories yet.</b>
              <p className="mute" style={{ fontSize: ".9rem" }}>
                Start a camera and they will appear here live.
              </p>
              <a className="btn shimmer" href="/cameras">
                Start a camera
              </a>
            </div>
          ) : (
            <AnimatedList
              items={recentMemories.map((m) => ({
                id: m.id,
                node: (
                  <div
                    style={{
                      borderRadius: 14,
                      border: "1px solid var(--line)",
                      background: "var(--bg)",
                      padding: "10px 14px",
                    }}
                  >
                    <p style={{ fontSize: ".92rem" }}>{m.scene?.summary ?? "Memory"}</p>
                    <p className="mono mute" style={{ marginTop: 4 }}>
                      {cameraNames[m.camera_id] ?? m.camera_id} ·{" "}
                      {new Date(m.timestamp).toLocaleString()}
                    </p>
                  </div>
                ),
              }))}
            />
          )}
        </div>

        <div className="panel" style={{ display: "grid", gap: 12, alignContent: "start" }}>
          <div className="flex items-center justify-between" style={{ gap: 12 }}>
            <b className="mono mute">RECENT EVENTS</b>
            <MessagesSquare size={16} aria-hidden="true" style={{ color: "var(--mute)" }} />
          </div>
          {events.isPending ? (
            <PanelSkeleton rows={3} />
          ) : events.isError ? (
            <PanelError message="Events are unavailable." onRetry={() => events.refetch()} />
          ) : recentEvents.length === 0 ? (
            <div style={{ display: "grid", gap: 10, justifyItems: "start" }}>
              <b>No events yet.</b>
              <a className="btn shimmer" href="/cameras">
                Start a camera
              </a>
            </div>
          ) : (
            <AnimatedList
              items={recentEvents.map((e) => ({
                id: e.id,
                node: (
                  <div
                    style={{
                      borderRadius: 14,
                      border: "1px solid var(--line)",
                      background: "var(--bg)",
                      padding: "10px 14px",
                    }}
                  >
                    <p style={{ fontSize: ".92rem" }}>
                      <span className="mono" style={{ color: "var(--acc)" }}>
                        {e.event_type}
                      </span>{" "}
                      · {e.description}
                    </p>
                    <p className="mono mute" style={{ marginTop: 4 }}>
                      {e.object_name} · {new Date(e.timestamp).toLocaleString()}
                    </p>
                  </div>
                ),
              }))}
            />
          )}
        </div>
      </div>
    </div>
  );
}
