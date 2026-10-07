"use client";

import { useCallback, useEffect, useState } from "react";

export interface CaptureSettings {
  /** Sampling rate target (frames per second). */
  fps: number;
  /** Downscale max side in px. */
  maxSide: number;
  /** JPEG quality 0..1. */
  quality: number;
  /** Local gate normalized threshold 0..1. */
  threshold: number;
  /** Gate cooldown window in seconds. */
  cooldownSeconds: number;
}

export const DEFAULT_CAPTURE: CaptureSettings = {
  fps: 2,
  maxSide: 1024,
  quality: 0.7,
  threshold: 0.06,
  cooldownSeconds: 8,
};

const CAPTURE_KEY = "vistara:capture";

function readStored(): CaptureSettings {
  try {
    const raw = window.localStorage.getItem(CAPTURE_KEY);
    if (!raw) return DEFAULT_CAPTURE;
    const parsed = JSON.parse(raw) as Partial<CaptureSettings>;
    return {
      fps: clampNum(parsed.fps, 1, 4, DEFAULT_CAPTURE.fps),
      maxSide: clampNum(parsed.maxSide, 256, 1024, DEFAULT_CAPTURE.maxSide),
      quality: clampNum(parsed.quality, 0.4, 0.95, DEFAULT_CAPTURE.quality),
      threshold: clampNum(parsed.threshold, 0.02, 0.2, DEFAULT_CAPTURE.threshold),
      cooldownSeconds: clampNum(
        parsed.cooldownSeconds,
        2,
        30,
        DEFAULT_CAPTURE.cooldownSeconds,
      ),
    };
  } catch {
    return DEFAULT_CAPTURE;
  }
}

function clampNum(
  value: unknown,
  min: number,
  max: number,
  fallback: number,
): number {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.min(max, Math.max(min, value))
    : fallback;
}

/**
 * Capture/gate settings live client-side in localStorage. Never sent to the
 * backend; no backend change required.
 */
export function useCaptureSettings() {
  const [settings, setSettings] = useState<CaptureSettings>(DEFAULT_CAPTURE);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Deferred a frame: the server renders defaults, and stored settings
    // hydrate right after without a mismatch.
    const frame = requestAnimationFrame(() => {
      setSettings(readStored());
      setReady(true);
    });
    return () => cancelAnimationFrame(frame);
  }, []);

  const update = useCallback((patch: Partial<CaptureSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      try {
        window.localStorage.setItem(CAPTURE_KEY, JSON.stringify(next));
      } catch {
        // Storage is best-effort (private mode, quotas).
      }
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    setSettings(DEFAULT_CAPTURE);
    try {
      window.localStorage.removeItem(CAPTURE_KEY);
    } catch {
      // Ignore.
    }
  }, []);

  return { settings, ready, update, reset };
}
