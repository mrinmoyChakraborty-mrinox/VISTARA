"use client";

import { useQuery } from "@tanstack/react-query";

import { useCamera } from "@/components/providers/camera-provider";
import { isEnvConfigured } from "@/lib/env";
import { getHealth } from "@/lib/apiClient";

function Chip({ dot, text }: { dot: string; text: string }) {
  return (
    <span className="schip">
      <span className={`sdot ${dot}`} aria-hidden="true" />
      {text}
    </span>
  );
}

/**
 * Global status strip: backend health, WebSocket connection state, and live
 * processing state. Vocabulary is limited to idle, connecting, connected,
 * disconnected, error, analyzing, and cooldown.
 */
export function StatusBar() {
  const { connection, processing, gateState, activeCameraId } = useCamera();

  const health = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    enabled: isEnvConfigured(),
    refetchInterval: 30_000,
    retry: false,
  });

  const backendDot = !isEnvConfigured()
    ? "amber"
    : health.isPending
      ? "amber"
      : health.isError
        ? "red"
        : "green";
  const backendText = !isEnvConfigured()
    ? "backend unconfigured"
    : health.isPending
      ? "backend checking"
      : health.isError
        ? "backend unreachable"
        : "backend connected";

  const socketDot =
    connection === "connected"
      ? "green"
      : connection === "connecting"
        ? "amber"
        : connection === "error"
          ? "red"
          : "";
  const processingDot = processing === "analyzing" ? "amber" : "";

  return (
    <div className="statusbar" role="status" aria-label="System status">
      <Chip dot={backendDot} text={backendText} />
      <Chip dot={socketDot} text={`socket ${connection}`} />
      {activeCameraId ? (
        <Chip dot={processingDot} text={processing} />
      ) : (
        <Chip dot="" text="idle" />
      )}
      {gateState === "cooldown" && <Chip dot="blue" text="cooldown" />}
    </div>
  );
}
