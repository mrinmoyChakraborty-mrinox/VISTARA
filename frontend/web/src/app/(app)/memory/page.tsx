"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { SearchX } from "lucide-react";

import { useCamera } from "@/components/providers/camera-provider";
import { MemoryCard } from "@/components/memory/memory-card";
import {
  applyMemoryFilters,
  EMPTY_FILTERS,
  MemoryFilters,
  type MemoryFilterValue,
} from "@/components/memory/memory-filters";
import { MemoryDetailDrawer } from "@/components/memory/memory-detail-drawer";
import { useCamerasQuery, useMemoriesQuery } from "@/hooks/use-cameras";
import type { Memory } from "@/types/domain";

const PAGE_SIZE = 20;

export default function MemoryPage() {
  const { sessionMemories } = useCamera();
  const memories = useMemoriesQuery();
  const cameras = useCamerasQuery();
  const [filters, setFilters] = useState<MemoryFilterValue>(EMPTY_FILTERS);
  const [visible, setVisible] = useState(PAGE_SIZE);
  const [selected, setSelected] = useState<Memory | null>(null);
  const sentinel = useRef<HTMLDivElement>(null);

  const cameraNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const camera of cameras.data ?? []) map[camera.id] = camera.name;
    return map;
  }, [cameras.data]);

  const eventTypes = useMemo(() => {
    const set = new Set<string>();
    for (const m of memories.data ?? []) {
      for (const e of m.events ?? []) set.add(e.event_type);
    }
    return [...set].sort();
  }, [memories.data]);

  const merged = useMemo(() => {
    const seen = new Set(sessionMemories.map((m) => m.id));
    const stored = (memories.data ?? []).filter((m) => !seen.has(m.id));
    return [...sessionMemories, ...stored].sort((a, b) =>
      a.created_at < b.created_at ? 1 : -1,
    );
  }, [sessionMemories, memories.data]);

  const filtered = useMemo(
    () => applyMemoryFilters(merged, filters),
    [merged, filters],
  );

  useEffect(() => {
    const el = sentinel.current;
    if (!el || filtered.length <= PAGE_SIZE) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible((v) => Math.min(v + PAGE_SIZE, filtered.length));
        }
      },
      { rootMargin: "400px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [filtered.length]);

  const shown = filtered.slice(0, visible);

  return (
    <div style={{ display: "grid", gap: 24 }}>
      <div>
        <h2>Memory</h2>
        <p className="mute" style={{ marginTop: 8 }}>
          Every saved moment, with the exact frame as proof. New memories slide
          in live.
        </p>
      </div>

      <div className="panel">
        <MemoryFilters
          cameras={(cameras.data ?? []).map((c) => ({ id: c.id, name: c.name }))}
          eventTypes={eventTypes}
          value={filters}
          onChange={(next) => {
            setFilters(next);
            setVisible(PAGE_SIZE);
          }}
        />
      </div>

      {memories.isPending ? (
        <div className="grid" style={{ gap: 14 }} role="status" aria-label="Loading memories">
          {[0, 1, 2].map((i) => (
            <div key={i} className="skel" style={{ height: 300, borderRadius: 22 }} />
          ))}
        </div>
      ) : memories.isError ? (
        <div role="alert" className="panel" style={{ display: "grid", gap: 10, justifyItems: "start" }}>
          <b>Memories could not be loaded.</b>
          <p className="mute" style={{ fontSize: ".9rem" }}>
            The backend may be unreachable. Session memories still arrive live.
          </p>
          <button type="button" className="btn" onClick={() => memories.refetch()}>
            Retry
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="panel" style={{ display: "grid", gap: 10, justifyItems: "start" }}>
          <SearchX size={22} aria-hidden="true" style={{ color: "var(--mute)" }} />
          {merged.length === 0 ? (
            <>
              <b>No memories yet.</b>
              <p className="mute" style={{ fontSize: ".9rem" }}>
                Start a camera and the loop will save its first memory.
              </p>
              <a className="btn shimmer" href="/cameras">
                Start a camera
              </a>
            </>
          ) : (
            <>
              <b>No memories match these filters.</b>
              <button
                type="button"
                className="btn"
                onClick={() => setFilters(EMPTY_FILTERS)}
              >
                Clear filters
              </button>
            </>
          )}
        </div>
      ) : (
        <div className="grid" style={{ gap: 14 }}>
          {shown.map((memory) => (
            <div key={memory.id} className="alist-item">
              <MemoryCard
                memory={memory}
                cameraName={cameraNames[memory.camera_id]}
                onOpen={setSelected}
              />
            </div>
          ))}
          <div ref={sentinel} aria-hidden="true" style={{ height: 1 }} />
          {visible < filtered.length && (
            <p className="mono mute" role="status" style={{ textAlign: "center" }}>
              Loading more… {shown.length} of {filtered.length}
            </p>
          )}
        </div>
      )}

      <MemoryDetailDrawer
        memory={selected}
        cameraName={selected ? cameraNames[selected.camera_id] : undefined}
        open={selected !== null}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}
