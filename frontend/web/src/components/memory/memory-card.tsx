"use client";

import { useState } from "react";

import { IndexingPill } from "@/components/memory/indexing-pill";
import { ObjectChip } from "@/components/memory/object-chip";
import { useEvidenceBlobUrl } from "@/hooks/use-evidence";
import type { Memory } from "@/types/domain";

export function formatMemoryTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

/**
 * One memory in the timeline: scene summary, object chips, event badges,
 * camera, confidence, timestamp, blur-up evidence thumbnail, indexing pill.
 */
export function MemoryCard({
  memory,
  cameraName,
  onOpen,
}: {
  memory: Memory;
  cameraName?: string;
  onOpen?: (memory: Memory) => void;
}) {
  const thumb = useEvidenceBlobUrl(memory.evidence_id);
  const [loaded, setLoaded] = useState(false);

  const open = () => onOpen?.(memory);

  return (
    <article
      onClick={open}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && onOpen) {
          e.preventDefault();
          open();
        }
      }}
      tabIndex={onOpen ? 0 : undefined}
      role={onOpen ? "button" : undefined}
      aria-label={onOpen ? `Open memory from ${formatMemoryTime(memory.timestamp)}` : undefined}
      className="spot"
      style={{
        borderRadius: 22,
        border: "1px solid var(--line)",
        background: "var(--card)",
        padding: 20,
        cursor: onOpen ? "pointer" : "default",
        display: "grid",
        gap: 12,
      }}
    >
      <div className="flex items-start justify-between" style={{ gap: 12 }}>
        <p style={{ fontWeight: 500 }}>{memory.scene?.summary ?? "Memory"}</p>
        <span className="mono mute" style={{ whiteSpace: "nowrap" }}>
          {Math.round((memory.confidence ?? 0) * 100)}%
        </span>
      </div>

      <div className="flex flex-wrap" style={{ gap: 6 }}>
        {(memory.objects ?? []).slice(0, 6).map((o) => (
          <ObjectChip key={o.id} name={o.name} />
        ))}
        {(memory.events ?? []).slice(0, 4).map((e) => (
          <span key={e.id} className="schip">
            <span className="sdot blue" aria-hidden="true" />
            {e.event_type}
          </span>
        ))}
      </div>

      <div
        aria-hidden="true"
        style={{
          borderRadius: 12,
          overflow: "hidden",
          border: "1px solid var(--line)",
          background: "linear-gradient(135deg, var(--desk), var(--soft))",
          aspectRatio: "16 / 8",
        }}
      >
        {thumb && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumb}
            alt=""
            onLoad={() => setLoaded(true)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: loaded ? "none" : "blur(10px)",
              transition: "filter .4s",
            }}
          />
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between" style={{ gap: 8 }}>
        <span className="mono mute">
          {formatMemoryTime(memory.timestamp)}
          {cameraName ? ` · ${cameraName}` : ""}
        </span>
        <IndexingPill memory={memory} />
      </div>
    </article>
  );
}
