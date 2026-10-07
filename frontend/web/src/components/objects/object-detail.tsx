"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { ArrowUpDown, Copy, Link as LinkIcon, MessageCircleQuestion } from "lucide-react";
import { toast } from "sonner";

import { useCamera } from "@/components/providers/camera-provider";
import { BorderBeam } from "@/components/ui-fx/border-beam";
import { useCamerasQuery } from "@/hooks/use-cameras";
import { useObjectHistoryQuery } from "@/hooks/use-memory";
import { EvidenceViewer } from "@/components/memory/evidence-viewer";
import type { ObjectObservation } from "@/lib/apiClient";
import { cn } from "@/lib/utils";

function CameraBadge({
  cameraId,
  names,
}: {
  cameraId: string;
  names: Record<string, string>;
}) {
  return <span className="schip">{names[cameraId] ?? cameraId}</span>;
}

function EvidenceThumb({
  observation,
  onOpen,
}: {
  observation: ObjectObservation;
  onOpen: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`Open evidence for ${observation.timestamp}`}
      style={{
        width: 72,
        height: 54,
        borderRadius: 10,
        border: "1px solid var(--line)",
        background: "linear-gradient(135deg, var(--desk), var(--soft))",
        cursor: "pointer",
        padding: 0,
      }}
    />
  );
}

export function ObjectDetail({ name }: { name: string }) {
  const router = useRouter();
  const { sessionMemories } = useCamera();
  const history = useObjectHistoryQuery(name);
  const cameras = useCamerasQuery();
  const [newestFirst, setNewestFirst] = useState(true);
  const [cameraFilter, setCameraFilter] = useState<string>("all");
  const [viewerFor, setViewerFor] = useState<ObjectObservation | null>(null);

  const cameraNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const camera of cameras.data ?? []) map[camera.id] = camera.name;
    return map;
  }, [cameras.data]);

  const liveExtras: ObjectObservation[] = useMemo(
    () =>
      sessionMemories
        .filter((m) =>
          (m.objects ?? []).some(
            (o) => o.normalized_name === name || o.name === name,
          ),
        )
        .map((m) => {
          const match = (m.objects ?? []).find(
            (o) => o.normalized_name === name || o.name === name,
          );
          return {
            memory_id: m.id,
            camera_id: m.camera_id,
            timestamp: m.timestamp,
            location: match?.location ?? "",
            status: match?.status ?? "",
            attributes: (match?.attributes ?? {}) as Record<string, unknown>,
          } satisfies ObjectObservation;
        }),
    [sessionMemories, name],
  );

  const observations = useMemo(() => {
    const seen = new Set(liveExtras.map((o) => `${o.memory_id}-${o.timestamp}`));
    const stored = (history.data ?? []).filter(
      (o) => !seen.has(`${o.memory_id}-${o.timestamp}`),
    );
    const all = [...liveExtras, ...stored];
    all.sort((a, b) =>
      newestFirst
        ? a.timestamp < b.timestamp
          ? 1
          : -1
        : a.timestamp < b.timestamp
          ? -1
          : 1,
    );
    return cameraFilter === "all"
      ? all
      : all.filter((o) => o.camera_id === cameraFilter);
  }, [liveExtras, history.data, newestFirst, cameraFilter]);

  const changes = useMemo(() => {
    const chrono = [...observations].sort((a, b) =>
      a.timestamp < b.timestamp ? -1 : 1,
    );
    return chrono.filter(
      (o, i) => i === 0 || o.location !== chrono[i - 1].location,
    );
  }, [observations]);

  const last = useMemo(() => {
    if (observations.length === 0) return null;
    return [...observations].sort((a, b) =>
      a.timestamp < b.timestamp ? 1 : -1,
    )[0];
  }, [observations]);

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(
        window.location.origin + `/objects/${encodeURIComponent(name)}`,
      );
      toast.success("Link copied", {
        description: "Share this object history with anyone on your account.",
      });
    } catch {
      toast.error("Could not copy the link");
    }
  };

  const askAbout = () => {
    router.push(`/chat?q=${encodeURIComponent(`Where did I last see the ${name}?`)}`);
  };

  return (
    <div style={{ display: "grid", gap: 24 }}>
      <div>
        <p className="mono mute">
          <Link href="/memory" style={{ textDecoration: "underline" }}>
            Memory
          </Link>{" "}
          / objects
        </p>
        <h2 style={{ marginTop: 8, overflowWrap: "anywhere" }}>{name}</h2>
      </div>

      {history.isPending ? (
        <div className="grid" style={{ gap: 12 }} role="status" aria-label="Loading object history">
          <div className="skel" style={{ height: 150, borderRadius: 22 }} />
          <div className="skel" style={{ height: 220, borderRadius: 22 }} />
        </div>
      ) : history.isError ? (
        <div role="alert" className="panel" style={{ display: "grid", gap: 10, justifyItems: "start" }}>
          <b>History could not be loaded.</b>
          <button type="button" className="btn" onClick={() => history.refetch()}>
            Retry
          </button>
        </div>
      ) : observations.length === 0 ? (
        <div className="panel" style={{ display: "grid", gap: 10, justifyItems: "start" }}>
          <b>No observations for “{name}” yet.</b>
          <p className="mute" style={{ fontSize: ".9rem" }}>
            When a camera last observes it, the trail starts here.
          </p>
          <a className="btn shimmer" href="/cameras">
            Open cameras
          </a>
        </div>
      ) : (
        <>
          {last && (
            <BorderBeam radius={24}>
              <div className="panel" style={{ border: 0, boxShadow: "none", background: "transparent" }}>
                <b className="mono mute">LAST OBSERVED</b>
                <p style={{ fontSize: "1.4rem", marginTop: 8 }}>
                  {last.location || "Unknown location"}
                </p>
                <p className="mono mute" style={{ marginTop: 4 }}>
                  {new Date(last.timestamp).toLocaleString()} ·{" "}
                  {cameraNames[last.camera_id] ?? last.camera_id}
                </p>
                <div className="flex flex-wrap" style={{ gap: 8, marginTop: 14 }}>
                  <button type="button" className="btn shimmer" onClick={askAbout}>
                    <MessageCircleQuestion size={15} aria-hidden="true" />
                    Ask about {name}
                  </button>
                  <button type="button" className="btn" onClick={copyLink}>
                    <Copy size={15} aria-hidden="true" />
                    Copy link
                  </button>
                </div>
              </div>
            </BorderBeam>
          )}

          <div className="panel" style={{ display: "grid", gap: 12 }}>
            <div className="flex flex-wrap items-center justify-between" style={{ gap: 10 }}>
              <b className="mono mute">TIMELINE</b>
              <div className="flex flex-wrap" style={{ gap: 8 }}>
                <button
                  type="button"
                  className="btn"
                  style={{ padding: "8px 14px", fontSize: ".85rem" }}
                  onClick={() => setNewestFirst((v) => !v)}
                  aria-pressed={!newestFirst}
                >
                  <ArrowUpDown size={14} aria-hidden="true" />
                  {newestFirst ? "Newest first" : "Oldest first"}
                </button>
              </div>
            </div>
            {Object.keys(cameraNames).length > 0 && (
              <div className="chips" style={{ margin: 0 }} role="group" aria-label="Filter by camera">
                <button
                  type="button"
                  className={cn("q", cameraFilter === "all" && "on")}
                  aria-pressed={cameraFilter === "all"}
                  onClick={() => setCameraFilter("all")}
                >
                  All cameras
                </button>
                {Object.entries(cameraNames).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    className={cn("q", cameraFilter === id && "on")}
                    aria-pressed={cameraFilter === id}
                    onClick={() => setCameraFilter(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
            <div className="tl" style={{ minHeight: 0 }}>
              {observations.map((row, k) => (
                <div
                  key={`${row.memory_id}-${row.timestamp}`}
                  style={{ animationDelay: `${Math.min(k, 8) * 0.15 + 0.15}s` }}
                >
                  <b className="mono">{new Date(row.timestamp).toLocaleString()}</b> —{" "}
                  {row.location || "Unknown location"}
                  <span style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
                    <CameraBadge cameraId={row.camera_id} names={cameraNames} />
                    {row.status && <span className="schip">{row.status}</span>}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="panel" style={{ display: "grid", gap: 12 }}>
            <b className="mono mute">LOCATION CHANGES</b>
            {changes.length <= 1 && observations[0]?.location ? (
              <p className="mute" style={{ fontSize: ".9rem" }}>
                Only one place so far — every move will be listed here.
              </p>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {changes.map((row) => (
                  <div
                    key={`c-${row.memory_id}-${row.timestamp}`}
                    className="alist-item"
                    style={{
                      borderRadius: 12,
                      border: "1px solid var(--line)",
                      background: "var(--bg)",
                      padding: "10px 14px",
                      fontSize: ".92rem",
                    }}
                  >
                    <span className="mono" style={{ color: "var(--acc)" }}>
                      {new Date(row.timestamp).toLocaleString()}
                    </span>{" "}
                    · {row.location || "Unknown location"}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="panel" style={{ display: "grid", gap: 12 }}>
            <b className="mono mute">EVIDENCE</b>
            <div className="flex flex-wrap" style={{ gap: 8 }}>
              {observations.slice(0, 8).map((row) => (
                <EvidenceThumb
                  key={`t-${row.memory_id}-${row.timestamp}`}
                  observation={row}
                  onOpen={() => setViewerFor(row)}
                />
              ))}
            </div>
            <p className="mute" style={{ fontSize: ".85rem" }}>
              <LinkIcon size={13} aria-hidden="true" style={{ verticalAlign: -2 }} /> Frames
              open in the shared viewer with camera, time, and description.
            </p>
          </div>
        </>
      )}

      <EvidenceViewer
        evidenceId={null}
        cameraName={viewerFor ? (cameraNames[viewerFor.camera_id] ?? viewerFor.camera_id) : undefined}
        timestamp={viewerFor ? new Date(viewerFor.timestamp).toLocaleString() : undefined}
        description={viewerFor ? `${name} · ${viewerFor.location}` : undefined}
        open={viewerFor !== null}
        onClose={() => setViewerFor(null)}
      />
    </div>
  );
}
