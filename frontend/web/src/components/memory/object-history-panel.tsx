"use client";

import type { ObjectObservation } from "@/lib/apiClient";

/**
 * Object history sub-view: chronological observations on a self-drawing
 * vertical line with sequential dot pop-in. Wording stays "last observed".
 */
export function ObjectHistoryPanel({
  observations,
  cameraNames,
  compact = false,
}: {
  observations: ObjectObservation[];
  cameraNames?: Record<string, string>;
  compact?: boolean;
}) {
  if (observations.length === 0) {
    return (
      <p className="mute" style={{ fontSize: ".9rem" }}>
        No observations for this object yet.
      </p>
    );
  }

  const ordered = [...observations].sort((a, b) =>
    a.timestamp < b.timestamp ? 1 : -1,
  );

  return (
    <div>
      {!compact && (
        <p className="mono mute" style={{ marginBottom: 8 }}>
          LAST OBSERVED{" "}
          {(() => {
            const last = ordered[0];
            const date = new Date(last.timestamp);
            return Number.isNaN(date.getTime()) ? last.timestamp : date.toLocaleString();
          })()}
        </p>
      )}
      <div className="tl" style={{ minHeight: 0 }}>
        {ordered.map((row, k) => (
          <div key={`${row.memory_id}-${row.timestamp}`} style={{ animationDelay: `${k * 0.2 + 0.2}s` }}>
            <b className="mono">{row.timestamp}</b> — {row.location}
            <span className="mono mute" style={{ display: "block" }}>
              {cameraNames?.[row.camera_id] ?? row.camera_id}
              {row.status ? ` · ${row.status}` : ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
