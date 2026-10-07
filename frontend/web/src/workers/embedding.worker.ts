// Client-side embedding worker: Qwen3-Embedding-0.6B via Transformers.js,
// ONNX Runtime Web, WebGPU when available with a WASM fallback. Never runs on
// the main thread. Emits 1024-dim vectors only — never frames.
import { pipeline, type FeatureExtractionPipeline } from "@huggingface/transformers";
type Device = "webgpu" | "wasm";

interface EmbedRequest {
  id: string;
  type: "embed";
  text: string;
  memoryId: string;
}

type Outgoing =
  | { id: string; type: "capability"; support: "webgpu" | "wasm" | "unsupported" }
  | { id: string; type: "progress"; progress: number; file: string; status: string }
  | { id: string; type: "result"; memoryId: string; vector: number[]; dims: number }
  | { id: string; type: "error"; memoryId?: string; message: string };

// Browser-ready ONNX build of the SAME Qwen3-Embedding-0.6B weights
// (the Qwen/Qwen3-Embedding-0.6B repo ships PyTorch only, which browsers
// cannot load — that id 404s under Transformers.js). q8 keeps the download
// small; output dims stay 1024.
const MODEL = "onnx-community/Qwen3-Embedding-0.6B-ONNX";
const DTYPE = "q8";
const DIMS = 1024;

let extractor: FeatureExtractionPipeline | null = null;
let device: Device = "wasm";

function post(message: Outgoing) {
  self.postMessage(message);
}

async function detectDevice(): Promise<Device> {
  try {
    const gpu = (navigator as Navigator & { gpu?: { requestAdapter: () => Promise<unknown> } }).gpu;
    if (!gpu) return "wasm";
    const adapter = await gpu.requestAdapter();
    return adapter ? "webgpu" : "wasm";
  } catch {
    return "wasm";
  }
}

async function loadExtractor(id: string): Promise<FeatureExtractionPipeline | null> {
  if (extractor) return extractor;
  device = await detectDevice();
  if (typeof WebAssembly === "undefined") {
    post({ id, type: "capability", support: "unsupported" });
    return null;
  }
  try {
    extractor = (await pipeline("feature-extraction", MODEL, {
      device,
      dtype: DTYPE,
      progress_callback: (info: unknown) => {
        const update = info as { progress?: number; file?: string; status?: string };
        // Forward every phase: initiate/download/done per file. "done" on the
        // last file still precedes ONNX session init, which emits nothing —
        // the UI shows "initializing" until capability arrives.
        post({
          id,
          type: "progress",
          progress: Math.round(update.progress ?? (update.status === "done" ? 100 : 0)),
          file: String(update.file ?? update.status ?? "model"),
          status: String(update.status ?? ""),
        });
      },
    })) as FeatureExtractionPipeline;
    post({ id, type: "capability", support: device });
    return extractor;
  } catch (err) {
    // Transparent WebGPU → WASM downgrade on runtime failure.
    if (device === "webgpu") {
      try {
        device = "wasm";
        extractor = (await pipeline("feature-extraction", MODEL, {
          device,
          dtype: DTYPE,
        })) as FeatureExtractionPipeline;
        post({ id, type: "capability", support: "wasm" });
        return extractor;
      } catch {
        // Fall through to the error below.
      }
    }
    post({
      id,
      type: "error",
      message: err instanceof Error ? err.message : "The embedding model could not load.",
    });
    return null;
  }
}

function toVector(output: unknown): number[] {
  const nested = output as { tolist?: () => number[][][] };
  const rows = typeof nested.tolist === "function" ? nested.tolist()[0] ?? [] : [];
  const width = rows[0]?.length ?? DIMS;
  const mean = new Array<number>(width).fill(0);
  if (rows.length === 0) return new Array<number>(DIMS).fill(0);
  for (const row of rows) {
    for (let i = 0; i < width; i += 1) mean[i] += row[i] ?? 0;
  }
  for (let i = 0; i < width; i += 1) mean[i] /= rows.length;
  if (width === DIMS) return mean;
  if (width > DIMS) return mean.slice(0, DIMS);
  return mean.concat(new Array<number>(DIMS - width).fill(0));
}

self.onmessage = async (event: MessageEvent<EmbedRequest>) => {
  const req = event.data;
  if (!req || req.type !== "embed") return;
  const pipe = await loadExtractor(req.id);
  if (!pipe) return;
  try {
    const output = await pipe(req.text, { pooling: "mean", normalize: false });
    const vector = toVector(output);
    post({ id: req.id, type: "result", memoryId: req.memoryId, vector, dims: vector.length });
  } catch (err) {
    post({
      id: req.id,
      type: "error",
      memoryId: req.memoryId,
      message: err instanceof Error ? err.message : "Embedding failed.",
    });
  }
};

export {};
