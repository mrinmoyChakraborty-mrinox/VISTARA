"use client";

import { useMemo } from "react";
import { Radio } from "lucide-react";

import { AnimatedList } from "@/components/ui-fx/animated-list";
import { useMemoriesQuery } from "@/hooks/use-cameras";
import { useEvidenceBlobUrl } from "@/hooks/use-evidence";
import type { Memory } from "@/types/domain";

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function MemoryFeedItem({
  memory,
  stamped,
}: {
  memory: Memory;
  stamped: boolean;
}) {
  const thumb = useEvidenceBlobUrl(memory.evidence_id);

  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        gap: 10,
        alignItems: "center",
        padding: 8,
        borderRadius: 12,
        border: "1px solid var(--line)",
        background: "var(--bg)",
      }}
    >
      <div
        aria-hidden="true"
        style={{
          width: 54,
          height: 40,
          borderRadius: 8,
          flex: "none",
          overflow: "hidden",
          background: "linear-gradient(135deg, var(--desk), var(--soft))",
        }}
      >
        {thumb && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumb}
            alt=""
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        )}
      </div>
      <div className="mono" style={{ minWidth: 0 }}>
        <span>{formatTime(memory.timestamp)}</span>
        <br />
        <span
          className="mute"
          style={{
            display: "block",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            maxWidth: 220,
          }}
        >
          {memory.scene?.summary ?? "Memory saved"}
        </span>
      </div>
      {stamped && (
        <span
          className="stamp stamp-in"
          style={{ position: "absolute", right: -6, top: -12 }}
        >
          SAVED
        </span>
      )}
    </div>
  );
}

/** Live session feed: socket memories first, then recent ones for the camera. */
export function LiveMemoryFeed({
  cameraId,
  session,
}: {
  cameraId: string;
  session: Memory[];
}) {
  const { data } = useMemoriesQuery();

  const items = useMemo(() => {
    const seen = new Set(session.map((m) => m.id));
    const stored = (data ?? []).filter(
      (m) => m.camera_id === cameraId && !seen.has(m.id),
    );
    return [...session, ...stored]
      .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
      .slice(0, 8);
  }, [session, data, cameraId]);

  if (items.length === 0) {
    return (
      <div
        className="panel"
        style={{ display: "grid", gap: 8, justifyItems: "start" }}
      >
        <Radio size={20} aria-hidden="true" style={{ color: "var(--mute)" }} />
        <b>No memories yet.</b>
        <p className="mute" style={{ fontSize: ".9rem" }}>
          Keep monitoring — new memories will slide in here the moment
          something moves.
        </p>
      </div>
    );
  }

  return (
    <div className="panel" style={{ display: "grid", gap: 12 }}>
      <b className="mono mute">LIVE MEMORY FEED</b>
      <AnimatedList
        items={items.map((memory) => ({
          id: memory.id,
          node: (
            <MemoryFeedItem
              memory={memory}
              stamped={session.some((m) => m.id === memory.id)}
            />
          ),
        }))}
      />
    </div>
  );
}
