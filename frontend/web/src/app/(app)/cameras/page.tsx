"use client";

import { useState } from "react";
import { Plus, VideoOff } from "lucide-react";

import { useCamera } from "@/components/providers/camera-provider";
import { CameraCard } from "@/components/cameras/camera-card";
import { CameraPreview } from "@/components/cameras/camera-preview";
import { LiveMemoryFeed } from "@/components/cameras/live-memory-feed";
import { NewCameraDialog } from "@/components/cameras/new-camera-dialog";
import { PairDialog } from "@/components/cameras/pair-dialog";
import { ProcessingBadge } from "@/components/cameras/processing-badge";
import { BrandLoader } from "@/components/loader/BrandLoader";
import {
  useCamerasQuery,
  useDeleteCamera,
  useStartCamera,
  useStopCamera,
} from "@/hooks/use-cameras";

function CameraGridSkeleton() {
  return (
    <>
      <BrandLoader variant="inline" />
      <div className="card-grid" role="status" aria-label="Loading cameras">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="skel"
            style={{ height: 220, borderRadius: 22 }}
          />
        ))}
      </div>
    </>
  );
}

export default function CamerasPage() {
  const { data: cameras, isPending, isError, refetch } = useCamerasQuery();
  const {
    activeCameraId,
    setActiveCameraId,
    disconnect,
    sessionMemories,
    socketError,
  } = useCamera();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [pairFor, setPairFor] = useState<{ id: string; name: string } | null>(null);

  const startMut = useStartCamera();
  const stopMut = useStopCamera();
  const deleteMut = useDeleteCamera();
  const busy = startMut.isPending || stopMut.isPending || deleteMut.isPending;

  const activeCamera = (cameras ?? []).find((c) => c.id === activeCameraId) ?? null;

  const onStart = (id: string) => {
    startMut.mutate(id, {
      onSuccess: () => setActiveCameraId(id),
    });
  };

  const onStop = (id: string) => {
    disconnect();
    setActiveCameraId(null);
    stopMut.mutate(id);
  };

  const onDelete = (id: string) => {
    if (id === activeCameraId) {
      disconnect();
      setActiveCameraId(null);
    }
    deleteMut.mutate(id);
  };

  return (
    <div>
      <div
        className="flex flex-wrap items-end justify-between"
        style={{ gap: 16 }}
      >
        <div>
          <h2>Cameras</h2>
          <p className="mute" style={{ marginTop: 8 }}>
            Connect a browser camera, watch the gate decide what matters, and
            see memories appear live.
          </p>
        </div>
        <button
          type="button"
          className="btn shimmer"
          onClick={() => setDialogOpen(true)}
        >
          <Plus size={16} aria-hidden="true" />
          New camera
        </button>
      </div>

      {isPending ? (
        <CameraGridSkeleton />
      ) : isError ? (
        <div
          role="alert"
          className="panel"
          style={{
            marginTop: 24,
            display: "grid",
            gap: 10,
            justifyItems: "start",
          }}
        >
          <b>Cameras could not be loaded.</b>
          <p className="mute" style={{ fontSize: ".9rem" }}>
            The backend may be unreachable. Your page and theme still work —
            retry when the backend is back.
          </p>
          <button type="button" className="btn" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      ) : !cameras || cameras.length === 0 ? (
        <div
          className="panel"
          style={{
            marginTop: 24,
            display: "grid",
            gap: 10,
            justifyItems: "start",
          }}
        >
          <VideoOff size={22} aria-hidden="true" style={{ color: "var(--mute)" }} />
          <b>No cameras yet.</b>
          <p className="mute" style={{ fontSize: ".9rem" }}>
            Add your first browser camera to start the watch–notice–remember
            loop.
          </p>
          <button
            type="button"
            className="btn shimmer"
            onClick={() => setDialogOpen(true)}
          >
            <Plus size={16} aria-hidden="true" />
            Add camera
          </button>
        </div>
      ) : (
        <div className="card-grid">
          {cameras.map((camera) => (
            <CameraCard
              key={camera.id}
              camera={camera}
              active={camera.id === activeCameraId}
              busy={busy}
              socketError={
                camera.id === activeCameraId ? socketError : null
              }
              onStart={() => onStart(camera.id)}
              onStop={() => onStop(camera.id)}
              onDelete={() => onDelete(camera.id)}
              onPair={() => setPairFor({ id: camera.id, name: camera.name })}
            />
          ))}
        </div>
      )}

      {activeCamera && (
        <div className="pv-grid">
          <CameraPreview key={activeCamera.id} camera={activeCamera} />
          <LiveMemoryFeed cameraId={activeCamera.id} session={sessionMemories} />
        </div>
      )}

      <ProcessingBadge />
      <NewCameraDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
      {pairFor && (
        <PairDialog
          cameraId={pairFor.id}
          cameraName={pairFor.name}
          open
          onClose={() => setPairFor(null)}
        />
      )}
    </div>
  );
}
