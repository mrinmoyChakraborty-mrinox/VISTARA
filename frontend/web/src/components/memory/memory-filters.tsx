"use client";

import { cn } from "@/lib/utils";

export interface MemoryFilterValue {
  cameraId: string | "all";
  range: "all" | "today" | "7d";
  eventType: string | "all";
  object: string;
  text: string;
}

export const EMPTY_FILTERS: MemoryFilterValue = {
  cameraId: "all",
  range: "all",
  eventType: "all",
  object: "",
  text: "",
};

const RANGES = [
  { key: "all", label: "All time" },
  { key: "today", label: "Today" },
  { key: "7d", label: "Last 7 days" },
] as const;

/**
 * Animated segmented tabs + chips. All filtering happens client-side over the
 * returned list, as the plan requires.
 */
export function MemoryFilters({
  cameras,
  eventTypes,
  value,
  onChange,
}: {
  cameras: { id: string; name: string }[];
  eventTypes: string[];
  value: MemoryFilterValue;
  onChange: (next: MemoryFilterValue) => void;
}) {
  const set = (patch: Partial<MemoryFilterValue>) =>
    onChange({ ...value, ...patch });

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div className="tabs" style={{ margin: 0 }} role="group" aria-label="Date range">
        {RANGES.map((range) => (
          <button
            key={range.key}
            type="button"
            className={cn(value.range === range.key && "on")}
            aria-pressed={value.range === range.key}
            onClick={() => set({ range: range.key })}
          >
            {range.label}
          </button>
        ))}
      </div>

      {cameras.length > 0 && (
        <div className="chips" style={{ margin: 0 }} role="group" aria-label="Camera">
          <button
            type="button"
            className={cn("q", value.cameraId === "all" && "on")}
            aria-pressed={value.cameraId === "all"}
            onClick={() => set({ cameraId: "all" })}
          >
            All cameras
          </button>
          {cameras.map((camera) => (
            <button
              key={camera.id}
              type="button"
              className={cn("q", value.cameraId === camera.id && "on")}
              aria-pressed={value.cameraId === camera.id}
              onClick={() => set({ cameraId: camera.id })}
            >
              {camera.name}
            </button>
          ))}
        </div>
      )}

      {eventTypes.length > 0 && (
        <div className="chips" style={{ margin: 0 }} role="group" aria-label="Event type">
          <button
            type="button"
            className={cn("q", value.eventType === "all" && "on")}
            aria-pressed={value.eventType === "all"}
            onClick={() => set({ eventType: "all" })}
          >
            All events
          </button>
          {eventTypes.map((type) => (
            <button
              key={type}
              type="button"
              className={cn("q", value.eventType === type && "on")}
              aria-pressed={value.eventType === type}
              onClick={() => set({ eventType: type })}
            >
              {type}
            </button>
          ))}
        </div>
      )}

      <div className="flex flex-wrap" style={{ gap: 10 }}>
        <div className="auth-field" style={{ flex: "1 1 180px" }}>
          <label htmlFor="memory-filter-object">Object</label>
          <input
            id="memory-filter-object"
            value={value.object}
            onChange={(e) => set({ object: e.target.value })}
            placeholder="ESP32, backpack…"
          />
        </div>
        <div className="auth-field" style={{ flex: "2 1 240px" }}>
          <label htmlFor="memory-filter-text">Search memories</label>
          <input
            id="memory-filter-text"
            value={value.text}
            onChange={(e) => set({ text: e.target.value })}
            placeholder="Describe what changed…"
          />
        </div>
      </div>
    </div>
  );
}

/** Apply the filter value client-side over a memory list. */
export function applyMemoryFilters<T extends {
  camera_id: string;
  timestamp: string;
  scene?: { summary?: string; activity?: string } | null;
  objects?: { name?: string; normalized_name?: string }[];
  events?: { event_type?: string; description?: string }[];
}>(list: T[], filters: MemoryFilterValue): T[] {
  const objectNeedle = filters.object.trim().toLowerCase();
  const textNeedle = filters.text.trim().toLowerCase();
  const now = Date.now();
  return list.filter((m) => {
    if (filters.cameraId !== "all" && m.camera_id !== filters.cameraId) return false;
    if (filters.range !== "all") {
      const t = new Date(m.timestamp).getTime();
      if (Number.isNaN(t)) return false;
      const days = filters.range === "today" ? 1 : 7;
      if (now - t > days * 24 * 60 * 60 * 1000) return false;
    }
    if (
      filters.eventType !== "all" &&
      !(m.events ?? []).some((e) => e.event_type === filters.eventType)
    ) {
      return false;
    }
    if (objectNeedle) {
      const hit = (m.objects ?? []).some(
        (o) =>
          (o.name ?? "").toLowerCase().includes(objectNeedle) ||
          (o.normalized_name ?? "").toLowerCase().includes(objectNeedle),
      );
      if (!hit) return false;
    }
    if (textNeedle) {
      const haystack = [
        m.scene?.summary ?? "",
        m.scene?.activity ?? "",
        ...(m.objects ?? []).map((o) => o.name ?? ""),
        ...(m.events ?? []).map((e) => e.description ?? ""),
      ]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(textNeedle)) return false;
    }
    return true;
  });
}
