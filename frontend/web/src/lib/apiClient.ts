// Typed REST client. Every protected call goes through apiFetch — never
// hand-roll headers in a component. Query params use URLSearchParams; the
// client never sends user_id (identity is derived server-side from the token).
import type {
  Camera,
  ChatMessage,
  Evidence,
  Memory,
  MemoryEvent,
  MemoryObject,
} from "@/types/domain";
import { getEnv, getVistaMode } from "@/lib/env";
import {
  getAccessToken,
  getSupabaseClient,
  setLocalToken,
} from "@/lib/supabaseClient";

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
  opts?: { token?: string | null; retried?: boolean; timeoutMs?: number },
): Promise<T> {
  const env = getEnv();
  const token = opts?.token ?? (await getAccessToken());
  // Every loader in the UI is bounded by this: a hung backend becomes an
  // error with retry instead of a spinner that never stops.
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    opts?.timeoutMs ?? 30_000,
  );
  let res: Response;
  try {
    res = await fetch(`${env.backendUrl}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch (err) {
    clearTimeout(timer);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw {
        status: 0,
        code: "timeout",
        message: "The backend did not respond in time. Retry when it is back.",
      } as ApiError;
    }
    throw {
      status: 0,
      code: "unreachable",
      message: "The backend could not be reached. Check the URL and retry.",
    } as ApiError;
  }
  clearTimeout(timer);
  if (res.status === 401 && !opts?.retried) {
    // Local demo mode has no Supabase session to refresh: drop the local
    // credential and bounce to login.
    if (getVistaMode() === "local") {
      setLocalToken(null);
      notifyUnauthorized();
      throw { status: 401, message: "Local demo session expired. Log in again." } as ApiError;
    }
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

export function createCamera(body: {
  name: string;
  source_type: string;
  config?: Record<string, unknown>;
}) {
  return apiFetch<Camera>("/api/cameras", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteCamera(id: string) {
  return apiFetch<void>(`/api/cameras/${id}`, { method: "DELETE" });
}

export function startCamera(id: string) {
  // The backend returns the updated camera (CameraOut), not a session record.
  return apiFetch<Camera>(`/api/cameras/${id}/start`, { method: "POST" });
}

export function stopCamera(id: string) {
  return apiFetch<Camera>(`/api/cameras/${id}/stop`, { method: "POST" });
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
  // Backend EmbeddingIn carries exactly { embedding }; nothing else.
  return apiFetch<unknown>(`/api/memories/${id}/embedding`, {
    method: "POST",
    body: JSON.stringify({ embedding: vector }),
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
  // The backend returns { object, first_seen, last_seen, entries[] } where
  // each entry is { timestamp, camera_id, location, status, memory_id }
  // (backend/app/retrieval/service.py::get_object_history). Entries carry no
  // attributes; observation attributes default to {}.
  const raw = payload as {
    observations?: unknown;
    memories?: unknown;
    entries?: unknown;
  };
  const list = Array.isArray(payload)
    ? payload
    : ((raw.observations ?? raw.memories ?? raw.entries ?? []) as unknown);
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
  // GPT-OSS reasons over retrieved memories; allow a longer budget before the
  // chat loader gives up.
  return apiFetch<ChatResponse>(
    "/api/chat",
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    { timeoutMs: 180_000 },
  );
}

// Evidence images are fetched with the bearer token and rendered as a blob
// URL. Callers must revoke the URL on unmount.
export async function fetchEvidenceBlob(
  id: string,
): Promise<{ url: string; revoke: () => void }> {
  const env = getEnv();
  const token = await getAccessToken();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30_000);
  let res: Response;
  try {
    res = await fetch(`${env.backendUrl}/api/evidence/${id}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: controller.signal,
    });
  } catch {
    clearTimeout(timer);
    throw {
      status: 0,
      code: "unreachable",
      message: "Evidence could not be loaded.",
    } as ApiError;
  }
  clearTimeout(timer);
  if (!res.ok) throw await toApiError(res);
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    // Local/offline fallback: the backend answers with metadata JSON
    // ({ id, storage_path, url: null }), not image bytes. Callers render an
    // honest "unavailable" state instead of a broken image.
    throw {
      status: 200,
      code: "evidence-unavailable",
      message: "This backend does not serve evidence files.",
    } as ApiError;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  return { url, revoke: () => URL.revokeObjectURL(url) };
}
