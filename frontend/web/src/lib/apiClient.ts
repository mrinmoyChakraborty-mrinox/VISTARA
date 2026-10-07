// Typed REST client. Every protected call goes through apiFetch — never
// hand-roll headers in a component. Query params use URLSearchParams; the
// client never sends user_id (identity is derived server-side from the token).
import type {
  Camera,
  CameraSession,
  ChatMessage,
  Evidence,
  Memory,
  MemoryEvent,
  MemoryObject,
} from "@/types/domain";
import { getEnv } from "@/lib/env";
import { getAccessToken, getSupabaseClient } from "@/lib/supabaseClient";

export interface ApiError {
  status: number;
  code?: string;
  message: string;
}

async function toApiError(res: Response): Promise<ApiError> {
  let code: string | undefined;
  let message = res.statusText || `Request failed (${res.status})`;
  try {
    const body = (await res.json()) as {
      message?: string;
      detail?: string;
      error?: string;
      code?: string;
    };
    message = body.message ?? body.detail ?? body.error ?? message;
    code = body.code;
  } catch {
    // Non-JSON error body; keep the status text.
  }
  return { status: res.status, code, message };
}

export const UNAUTHORIZED_EVENT = "vistara:unauthorized";

/**
 * The API layer never navigates itself. On an unrecoverable 401 it signs out
 * best-effort and notifies the AuthProvider, which redirects to /login.
 */
function notifyUnauthorized() {
  if (typeof window === "undefined") return;
  const next = window.location.pathname + window.location.search;
  window.dispatchEvent(
    new CustomEvent<string>(UNAUTHORIZED_EVENT, { detail: next }),
  );
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  opts?: { token?: string | null; retried?: boolean },
): Promise<T> {
  const env = getEnv();
  const token = opts?.token ?? (await getAccessToken());
  const res = await fetch(`${env.backendUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (res.status === 401 && !opts?.retried) {
    try {
      const supabase = getSupabaseClient();
      const { data } = await supabase.auth.refreshSession();
      const refreshed = data.session?.access_token ?? null;
      if (refreshed) {
        return apiFetch<T>(path, init, { ...opts, token: refreshed, retried: true });
      }
    } catch {
      // Fall through to sign-out below.
    }
    try {
      await getSupabaseClient().auth.signOut();
    } catch {
      // Signing out is best-effort here.
    }
    notifyUnauthorized();
    throw { status: 401, message: "Session expired. Please log in again." } as ApiError;
  }
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

function withParams(
  params?: Record<string, string | number | boolean | undefined>,
): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

// Endpoint usage map (frozen paths; filters stay optional so the client keeps
// working when the backend only supports plain GET).
export function getHealth() {
  return apiFetch<{ status: string }>("/api/health");
}

export function listCameras() {
  return apiFetch<Camera[]>("/api/cameras");
}

export function createCamera(body: { name: string; source_type: "browser" }) {
  return apiFetch<Camera>("/api/cameras", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteCamera(id: string) {
  return apiFetch<void>(`/api/cameras/${id}`, { method: "DELETE" });
}

export function startCamera(id: string) {
  return apiFetch<CameraSession>(`/api/cameras/${id}/start`, { method: "POST" });
}

export function stopCamera(id: string) {
  return apiFetch<CameraSession>(`/api/cameras/${id}/stop`, { method: "POST" });
}

export function listMemories(
  params?: Record<string, string | number | boolean | undefined>,
) {
  return apiFetch<Memory[]>(`/api/memories${withParams(params)}`);
}

export function getMemory(id: string) {
  return apiFetch<Memory>(`/api/memories/${id}`);
}

export function postEmbedding(id: string, vector: number[]) {
  return apiFetch<unknown>(`/api/memories/${id}/embedding`, {
    method: "POST",
    body: JSON.stringify({ embedding: vector, dims: vector.length }),
  });
}

export interface ObjectObservation {
  memory_id: string;
  camera_id: string;
  timestamp: string;
  location: string;
  status: string;
  attributes: Record<string, unknown>;
}

function toObservations(payload: unknown, name: string): ObjectObservation[] {
  const list = Array.isArray(payload)
    ? payload
    : ((payload as { observations?: unknown }).observations ??
      (payload as { memories?: unknown }).memories ??
      []);
  if (!Array.isArray(list)) return [];
  const out: ObjectObservation[] = [];
  for (const entry of list) {
    const row = entry as Partial<ObjectObservation> & {
      memory?: Partial<Memory>;
      objects?: Partial<MemoryObject>[];
    };
    if (row.memory_id && row.timestamp !== undefined) {
      out.push({
        memory_id: String(row.memory_id),
        camera_id: String(row.camera_id ?? ""),
        timestamp: String(row.timestamp),
        location: String(row.location ?? ""),
        status: String(row.status ?? ""),
        attributes: (row.attributes ?? {}) as Record<string, unknown>,
      });
      continue;
    }
    const memory = row.memory ?? (row as Partial<Memory>);
    const objects: Partial<MemoryObject>[] =
      row.objects ?? (memory as Partial<Memory>).objects ?? [];
    const match = objects.find(
      (o) => o.normalized_name === name || o.name === name,
    );
    if (memory && match) {
      out.push({
        memory_id: String((memory as { id?: string }).id ?? ""),
        camera_id: String((memory as { camera_id?: string }).camera_id ?? ""),
        timestamp: String((memory as { timestamp?: string }).timestamp ?? ""),
        location: String(match.location ?? ""),
        status: String(match.status ?? ""),
        attributes: (match.attributes ?? {}) as Record<string, unknown>,
      });
    }
  }
  return out;
}

export async function getObjectHistory(
  name: string,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<ObjectObservation[]> {
  const payload = await apiFetch<unknown>(
    `/api/objects/${encodeURIComponent(name)}/history${withParams(params)}`,
  );
  return toObservations(payload, name);
}

export function listEvents(
  params?: Record<string, string | number | boolean | undefined>,
) {
  return apiFetch<MemoryEvent[]>(`/api/events${withParams(params)}`);
}

export interface ChatResponse {
  conversation_id: string;
  answer: string;
  evidence: Evidence[];
  tool_calls: ChatMessage["tool_calls"];
}

export function postChat(body: { conversation_id?: string; message: string }) {
  return apiFetch<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// Evidence images are fetched with the bearer token and rendered as a blob
// URL. Callers must revoke the URL on unmount.
export async function fetchEvidenceBlob(
  id: string,
): Promise<{ url: string; revoke: () => void }> {
  const env = getEnv();
  const token = await getAccessToken();
  const res = await fetch(`${env.backendUrl}/api/evidence/${id}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw await toApiError(res);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  return { url, revoke: () => URL.revokeObjectURL(url) };
}
