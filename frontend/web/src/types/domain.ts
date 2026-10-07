// Backend domain types — kept in sync with backend Pydantic schemas
// (backend/app/api/cameras.py::CameraOut, backend/app/memory/schemas.py).
// Fields the backend never sends are not declared here.

export type CameraStatus = "idle" | "active" | "disconnected" | "error";

/** Registered backend source types (backend/app/cameras/factory.py). */
export type CameraSourceType =
  | "browser"
  | "phone"
  | "rtsp"
  | "rtsps"
  | "hls"
  | "mjpeg";

export interface Camera {
  id: string;
  name: string;
  source_type: CameraSourceType | string;
  status: CameraStatus;
  config: Record<string, unknown>;
  created_at: string;
  last_seen_at: string | null;
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
  /** True for the initial semantic visual baseline (not a movement event). */
  is_baseline: boolean;
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
