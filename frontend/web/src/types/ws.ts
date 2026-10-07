import type { Memory } from "@/types/domain";

// WebSocket contract — frozen shapes from the Frontend Plan.
// Client to server: camera_connected, frame, stop. Nothing else is ever sent.
export type WsClientMessage =
  | { type: "camera_connected" }
  | { type: "frame"; data: string; ts: number }
  | { type: "stop" };

// Server to client: the five handled message types.
export type WsServerMessage =
  | { type: "connection_state"; state: "connected" | "disconnected" | "error" }
  | { type: "processing"; state: "idle" | "analyzing" }
  | { type: "change_detected"; score: number }
  | { type: "memory_created"; memory: Memory }
  | { type: "error"; message: string };

// Client-only helper types (frontend-internal, not backend contracts).
export type WsConnectionState =
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

export type ProcessingState = "idle" | "analyzing";

export type LocalGateState = "idle" | "buffering" | "triggered" | "cooldown";

export interface LocalChangeResult {
  changed: boolean;
  score: number;
}

export type WebGpuSupport = "webgpu" | "wasm" | "unsupported";
