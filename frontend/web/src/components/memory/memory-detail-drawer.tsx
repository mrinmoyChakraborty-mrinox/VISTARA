"use client";

import { useState } from "react";

import { EvidenceViewer } from "@/components/memory/evidence-viewer";
import { ObjectChip } from "@/components/memory/object-chip";
import { formatMemoryTime } from "@/components/memory/memory-card";
import { Sheet, SheetTitle } from "@/components/ui/sheet";
import type { Memory } from "@/types/domain";

/** Full memory in a shadcn Sheet with staggered content reveal. */
export function MemoryDetailDrawer({
  memory,
  cameraName,
  open,
  onClose,
}: {
  memory: Memory | null;
  cameraName?: string;
  open: boolean;
  onClose: () => void;
}) {
  const [viewerOpen, setViewerOpen] = useState(false);

  return (
    <>
      <Sheet open={open} onOpenChange={(next) => !next && onClose()} labelledBy="memory-detail-title">
        {memory && (
          <div className="sheet-stagger" style={{ display: "grid", gap: 16 }}>
            <SheetTitle id="memory-detail-title">
              {memory.scene?.summary ?? "Memory"}
            </SheetTitle>
            <p className="mono mute">
              {formatMemoryTime(memory.timestamp)}
              {cameraName ? ` · ${cameraName}` : ""}
            </p>
            <div>
              <b className="mono mute">SCENE</b>
              <p style={{ marginTop: 6 }}>
                {memory.scene?.activity ?? "No scene description."}{" "}
                <span className="mute">{memory.scene?.environment ?? ""}</span>
              </p>
            </div>
            <div>
              <b className="mono mute">OBJECTS</b>
              <div className="flex flex-wrap" style={{ gap: 6, marginTop: 8 }}>
                {(memory.objects ?? []).map((o) => (
                  <ObjectChip
                    key={o.id}
                    name={`${o.name} · ${o.location}`}
                    href={`/objects/${encodeURIComponent(o.normalized_name || o.name)}`}
                  />
                ))}
                {(memory.objects ?? []).length === 0 && (
                  <span className="mute" style={{ fontSize: ".9rem" }}>
                    No objects recorded.
                  </span>
                )}
              </div>
            </div>
            <div>
              <b className="mono mute">EVENTS</b>
              <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                {(memory.events ?? []).map((e) => (
                  <div
                    key={e.id}
                    style={{
                      borderRadius: 12,
                      border: "1px solid var(--line)",
                      background: "var(--bg)",
                      padding: "10px 12px",
                      fontSize: ".9rem",
                    }}
                  >
                    <span className="mono" style={{ color: "var(--acc)" }}>
                      {e.event_type}
                    </span>{" "}
                    · {e.description}
                    <span className="mono mute" style={{ display: "block", marginTop: 4 }}>
                      {e.object_name} · {Math.round((e.confidence ?? 0) * 100)}%
                    </span>
                  </div>
                ))}
                {(memory.events ?? []).length === 0 && (
                  <span className="mute" style={{ fontSize: ".9rem" }}>
                    No events recorded.
                  </span>
                )}
              </div>
            </div>
            <div>
              <b className="mono mute">EVIDENCE</b>
              <div style={{ marginTop: 8 }}>
                <button
                  type="button"
                  className="btn"
                  onClick={() => setViewerOpen(true)}
                >
                  Open evidence frame
                </button>
              </div>
            </div>
          </div>
        )}
      </Sheet>
      {memory && (
        <EvidenceViewer
          evidenceId={memory.evidence_id}
          cameraName={cameraName}
          timestamp={formatMemoryTime(memory.timestamp)}
          description={memory.scene?.summary}
          open={viewerOpen}
          onClose={() => setViewerOpen(false)}
        />
      )}
    </>
  );
}
