// Local change gate: decides whether a sampled frame is worth sending.
// Pipeline: grayscale thumbnail mean-absolute-difference against the previous
// thumbnail, a persistence check over consecutive samples, then a cooldown.
// The backend gate stays authoritative; this only saves bandwidth.
import type { LocalChangeResult, LocalGateState } from "@/types/ws";

export interface GateConfig {
  /** Minimum normalized diff (0..1) to count as change. */
  threshold: number;
  /** Consecutive changed samples before triggering. Default 2. */
  persistenceFrames?: number;
  /** Suppression window after an event, in seconds. Default 8. */
  cooldownSeconds?: number;
}

/** Normalized mean absolute difference between two thumbnails (0..1). */
export function thumbnailDiff(
  prev: Uint8ClampedArray,
  curr: Uint8ClampedArray,
): number {
  const n = Math.min(prev.length, curr.length);
  if (n === 0) return 0;
  let sum = 0;
  for (let i = 0; i < n; i += 1) sum += Math.abs(curr[i] - prev[i]);
  return sum / n / 255;
}

export class ChangeGate {
  private readonly persistence: number;
  private readonly cooldownMs: number;
  private readonly threshold: number;
  private consecutive = 0;
  private triggeredAt = 0;
  private prev: Uint8ClampedArray | null = null;
  state: LocalGateState = "idle";

  constructor(config: GateConfig) {
    this.threshold = config.threshold;
    this.persistence = config.persistenceFrames ?? 2;
    this.cooldownMs = (config.cooldownSeconds ?? 8) * 1000;
  }

  /** Feed one thumbnail; returns whether a frame should be uploaded. */
  push(pixels: Uint8ClampedArray, now = Date.now()): LocalChangeResult {
    if (this.prev && this.prev.length === pixels.length) {
      const score = thumbnailDiff(this.prev, pixels);
      this.prev = pixels;
      return this.score(score, now);
    }
    this.prev = pixels;
    this.state = "idle";
    this.consecutive = 0;
    return { changed: false, score: 0 };
  }

  /** Feed a precomputed normalized score (0..1). */
  score(raw: number, now = Date.now()): LocalChangeResult {
    const score = Math.min(1, Math.max(0, raw));
    if (now - this.triggeredAt < this.cooldownMs) {
      this.state = "cooldown";
      this.consecutive = 0;
      return { changed: false, score };
    }
    if (score >= this.threshold) {
      this.consecutive += 1;
      if (this.consecutive >= this.persistence) {
        this.state = "triggered";
        this.triggeredAt = now;
        this.consecutive = 0;
        return { changed: true, score };
      }
      this.state = "buffering";
      return { changed: false, score };
    }
    this.state = "idle";
    this.consecutive = 0;
    return { changed: false, score };
  }

  reset() {
    this.state = "idle";
    this.consecutive = 0;
    this.triggeredAt = 0;
    this.prev = null;
  }
}
