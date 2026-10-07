// Frozen backend domain types — reproduced verbatim from the Frontend Plan.
// Do not rename fields. Do not add required fields.

export type CameraStatus = "idle" | "active" | "disconnected" | "error";

export interface Camera {
  id: string;
  user_id: string;
  name: string;
  source_type: "browser" | "rtsp";
  status: CameraStatus;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  last_seen_at: string | null;
}

export type CameraSessionStatus = "started" | "stopped" | "error";

export interface CameraSession {
  id: string;
  camera_id: string;
  user_id: string;
  started_at: string;
  ended_at: string | null;
  status: CameraSessionStatus;
}

export interface Scene {
  type: string;
  summary: string;
  activity: string;
  environment: string;
}

export interface MemoryObject {
  id: string;
  memory_id: string;
  name: string;
  normalized_name: string;
  location: string;
  status: string;
  attributes: Record<string, unknown>;
}

export interface MemoryEvent {
  id: string;
  memory_id: string;
  camera_id: string;
  timestamp: string;
  event_type: string;
  object_name: string;
  from_location: string;
  to_location: string;
  description: string;
  confidence: number;
}

export interface Evidence {
  id: string;
  memory_id: string;
  camera_id: string;
  timestamp: string;
  storage_path: string;
  mime_type: string;
  url?: string;
}

export interface Memory {
  id: string;
  camera_id: string;
  timestamp: string;
  scene: Scene;
  objects: MemoryObject[];
  events: MemoryEvent[];
  confidence: number;
  evidence_id: string | null;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  tool_calls: ToolResult[] | null;
  created_at: string;
}

export interface ToolResult {
  tool: string;
  args: Record<string, unknown>;
  result: unknown;
}
