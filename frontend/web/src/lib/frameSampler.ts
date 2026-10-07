// Frame sampling: ~2 FPS cadence is enforced by the caller. This module
// downscales to a max side of ~1024px, encodes JPEG base64, and strips the
// data-URL prefix before sending (the socket only accepts raw base64).

export interface SampledFrame {
  /** Raw base64 JPEG, data-URL prefix stripped. */
  data: string;
  /** Approximate encoded bytes on the wire. */
  bytes: number;
  width: number;
  height: number;
}

export const SAMPLE_MAX_SIDE = 1024;
export const SAMPLE_JPEG_QUALITY = 0.7;

let sharedCanvas: HTMLCanvasElement | null = null;

function getCanvas(): HTMLCanvasElement {
  if (!sharedCanvas) sharedCanvas = document.createElement("canvas");
  return sharedCanvas;
}

/** Sample one frame from a live <video>. Returns null when not ready. */
export function sampleFrame(
  video: HTMLVideoElement,
  maxSide = SAMPLE_MAX_SIDE,
  quality = SAMPLE_JPEG_QUALITY,
): SampledFrame | null {
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  if (!vw || !vh || video.readyState < 2) return null;
  const scale = Math.min(1, maxSide / Math.max(vw, vh));
  const width = Math.max(1, Math.round(vw * scale));
  const height = Math.max(1, Math.round(vh * scale));
  const canvas = getCanvas();
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(video, 0, 0, width, height);
  const dataUrl = canvas.toDataURL("image/jpeg", quality);
  const data = dataUrl.split(",")[1] ?? "";
  if (!data) return null;
  return { data, bytes: Math.floor((data.length * 3) / 4), width, height };
}

/** Small grayscale thumbnail for the local change gate. */
export function toGrayscaleThumbnail(
  source: HTMLVideoElement | HTMLCanvasElement,
  size = 48,
): { pixels: Uint8ClampedArray; width: number; height: number } | null {
  const vw =
    source instanceof HTMLVideoElement ? source.videoWidth : source.width;
  const vh =
    source instanceof HTMLVideoElement ? source.videoHeight : source.height;
  if (!vw || !vh) return null;
  const canvas = getCanvas();
  canvas.width = size;
  canvas.height = Math.max(1, Math.round((size * vh) / vw));
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;
  ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
  const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const pixels = new Uint8ClampedArray(canvas.width * canvas.height);
  for (let i = 0; i < pixels.length; i += 1) {
    const o = i * 4;
    pixels[i] = Math.round(
      0.299 * image.data[o] + 0.587 * image.data[o + 1] + 0.114 * image.data[o + 2],
    );
  }
  return { pixels, width: canvas.width, height: canvas.height };
}
