// Background embedding queue. Memory display and chat never wait for it:
// memories render immediately, an IndexingPill tracks the background POST,
// and failures surface as a retry pill. Only the 1024-dim vector is ever
// uploaded — never frames.
import { postEmbedding } from "@/lib/apiClient";
import { isEnvConfigured } from "@/lib/env";
import type { Memory } from "@/types/domain";
import type { WebGpuSupport } from "@/types/ws";

export type IndexStatus = "indexing" | "done" | "error";

interface QueueState {
  statusById: Record<string, IndexStatus>;
  capability: WebGpuSupport | "unknown";
  modelState: "idle" | "loading" | "ready" | "error";
  progress: number;
  progressFile: string;
}

type Listener = (state: QueueState) => void;

const state: QueueState = {
  statusById: {},
  capability: "unknown",
  modelState: "idle",
  progress: 0,
  progressFile: "",
};

const listeners = new Set<Listener>();
let worker: Worker | null = null;
let seq = 0;
const pending = new Map<
  string,
  { memoryId: string; resolve: (v: number[]) => void; reject: (e: Error) => void }
>();

function emit() {
  const snapshot: QueueState = {
    ...state,
    statusById: { ...state.statusById },
  };
  listeners.forEach((fn) => fn(snapshot));
}

export function subscribeEmbedding(listener: Listener): () => void {
  listeners.add(listener);
  listener({
    ...state,
    statusById: { ...state.statusById },
  });
  return () => {
    listeners.delete(listener);
  };
}

export function getEmbeddingState(): QueueState {
  return { ...state, statusById: { ...state.statusById } };
}

function ensureWorker(): Worker | null {
  if (worker || typeof window === "undefined") return worker;
  try {
    worker = new Worker(new URL("../workers/embedding.worker.ts", import.meta.url));
  } catch {
    state.capability = "unsupported";
    emit();
    return null;
  }
  worker.onmessage = (event: MessageEvent) => {
    const msg = event.data as
      | { type: "capability"; support: WebGpuSupport; id: string }
      | { type: "progress"; progress: number; file: string; id: string }
      | { type: "result"; memoryId: string; vector: number[]; id: string }
      | { type: "error"; message: string; memoryId?: string; id: string };
    if (msg.type === "capability") {
      state.capability = msg.support;
      if (msg.support !== "unsupported") state.modelState = "ready";
      else state.modelState = "error";
      emit();
      return;
    }
    if (msg.type === "progress") {
      state.modelState = "loading";
      state.progress = msg.progress;
      state.progressFile = msg.file;
      emit();
      return;
    }
    const job = pending.get(msg.id);
    if (!job) return;
    pending.delete(msg.id);
    if (msg.type === "result") {
      state.modelState = "ready";
      emit();
      job.resolve(msg.vector);
    } else {
      job.reject(new Error(msg.message));
    }
  };
  worker.onerror = () => {
    state.modelState = "error";
    emit();
  };
  return worker;
}

function embedText(text: string, memoryId: string): Promise<number[]> {
  const w = ensureWorker();
  if (!w) return Promise.reject(new Error("Embedding is unsupported here."));
  state.modelState = "loading";
  emit();
  return new Promise<number[]>((resolve, reject) => {
    const id = `embed-${Date.now()}-${(seq += 1)}`;
    pending.set(id, { memoryId, resolve, reject });
    w.postMessage({ id, type: "embed", text, memoryId });
  });
}

function semanticText(memory: Memory): string {
  const objects = (memory.objects ?? [])
    .map((o) => `${o.name} at ${o.location}`)
    .join("; ");
  const events = (memory.events ?? []).map((e) => e.description).join("; ");
  return `${memory.scene?.summary ?? ""} | ${objects} | ${events}`;
}

/** Queue one memory for background indexing. Never throws. */
export async function queueIndexing(memory: Memory): Promise<void> {
  if (!isEnvConfigured()) return;
  if (state.statusById[memory.id] === "indexing") return;
  state.statusById[memory.id] = "indexing";
  emit();
  try {
    const vector = await embedText(semanticText(memory), memory.id);
    await postEmbedding(memory.id, vector);
    state.statusById[memory.id] = "done";
  } catch {
    state.statusById[memory.id] = "error";
  }
  emit();
}

/** Drop the worker (clears the in-memory pipeline) so it reloads on demand. */
export function reloadEmbeddingModel() {
  try {
    worker?.terminate();
  } catch {
    // Best-effort.
  }
  worker = null;
  pending.clear();
  state.modelState = "idle";
  state.progress = 0;
  state.progressFile = "";
  emit();
}
