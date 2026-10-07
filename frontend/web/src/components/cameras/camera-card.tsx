"use client";

import { useState } from "react";
import { Play, Square, Trash2 } from "lucide-react";

import { SpotlightCard } from "@/components/ui-fx/spotlight-card";
import type { Camera, CameraStatus } from "@/types/domain";
import { cn } from "@/lib/utils";

const STATUS_DOT: Record<CameraStatus, string> = {
  idle: "",
  active: "green",
  disconnected: "amber",
  error: "red",
};

function formatLastSeen(value: string | null): string {
  if (!value) return "never seen";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "never seen";
  return `last seen ${date.toLocaleString()}`;
}

export function CameraCard({
  camera,
  active,
  busy,
  socketError,
  onStart,
  onStop,
  onDelete,
}: {
  camera: Camera;
  active: boolean;
  busy: boolean;
  socketError: string | null;
  onStart: () => void;
  onStop: () => void;
  onDelete: () => void;
}) {
  const [confirming, setConfirming] = useState(false);

  return (
    <SpotlightCard
      className={cn(
        "rounded-[22px] border border-line bg-card p-6",
        active && "outline outline-2 outline-[var(--acc)]",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 style={{ fontSize: "1.2rem" }}>{camera.name}</h3>
          <p className="mono mute" style={{ marginTop: 4 }}>
            {camera.id.slice(0, 8)} · {camera.source_type}
          </p>
        </div>
        <span className="schip">
          <span className={`sdot ${STATUS_DOT[camera.status]}`} aria-hidden="true" />
          {camera.status}
        </span>
      </div>
      <p className="mono mute" style={{ marginTop: 10 }}>
        {formatLastSeen(camera.last_seen_at)}
      </p>
      {active && socketError && (
        <p role="alert" className="mono" style={{ color: "#c4572f", marginTop: 8 }}>
          {socketError}
        </p>
      )}
      <div className="flex flex-wrap gap-2" style={{ marginTop: 16 }}>
        {active ? (
          <button type="button" className="btn" onClick={onStop} disabled={busy}>
            <Square size={15} aria-hidden="true" />
            Stop
          </button>
        ) : (
          <button
            type="button"
            className="btn shimmer"
            onClick={onStart}
            disabled={busy}
          >
            <Play size={15} aria-hidden="true" />
            Start
          </button>
        )}
        {confirming ? (
          <>
            <button
              type="button"
              className="btn"
              onClick={() => {
                setConfirming(false);
                onDelete();
              }}
              disabled={busy}
              autoFocus
            >
              Confirm delete
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => setConfirming(false)}
              disabled={busy}
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            type="button"
            className="btn"
            onClick={() => setConfirming(true)}
            disabled={busy}
            aria-label={`Delete camera ${camera.name}`}
          >
            <Trash2 size={15} aria-hidden="true" />
            Delete
          </button>
        )}
      </div>
    </SpotlightCard>
  );
}
