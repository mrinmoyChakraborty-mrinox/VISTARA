"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const STATUS_MESSAGES = [
  "Waking the camera",
  "Loading memories",
  "Warming up search",
];

const BLADES = [0, 1, 2, 3, 4, 5, 6, 7];

/**
 * Aperture Memory Loader. Full variant is a fixed overlay with the iris
 * ring, mask-filling wordmark, viewfinder corners, scan sweep, rotating
 * status line, and bottom hairline. Inline is the same lockup compact and
 * static-positioned for page-level loading states.
 *
 * progress is 0..1 and drives the wordmark fill + hairline for real. When
 * omitted, the loader is indeterminate (full wordmark + sweeping hairline).
 */
export function BrandLoader({
  variant = "full",
  progress,
  leaving = false,
}: {
  variant?: "full" | "inline";
  progress?: number;
  leaving?: boolean;
}) {
  const determinate = typeof progress === "number";
  const pct = determinate ? Math.min(1, Math.max(0, progress)) : 0;
  const [statusIdx, setStatusIdx] = useState(0);

  useEffect(() => {
    if (variant !== "full") return;
    const id = window.setInterval(() => {
      setStatusIdx((i) => (i + 1) % STATUS_MESSAGES.length);
    }, 900);
    return () => window.clearInterval(id);
  }, [variant]);

  return (
    <div
      className={cn("boot", variant === "inline" ? "boot-inline" : "boot-full")}
      data-leaving={leaving || undefined}
      role="status"
      aria-live="polite"
      aria-busy={!leaving}
    >
      <span className="sr-only">Loading Vistara</span>

      <div className="boot-stage" aria-hidden="true">
        <svg
          className="boot-aperture"
          viewBox="0 0 160 160"
          focusable="false"
        >
          <g className="boot-blades">
            <circle cx="80" cy="80" r="72" className="boot-ring" />
            {BLADES.map((i) => (
              <path
                key={i}
                d="M80 18 Q104 30 118 58"
                className="boot-blade"
                style={{ opacity: i % 2 ? 0.55 : 1 }}
                transform={`rotate(${i * 45} 80 80)`}
              />
            ))}
            <circle cx="80" cy="80" r="34" className="boot-ring boot-acc" />
          </g>
        </svg>

        <span className="boot-lockup">
          <span className="boot-emblem">
            <span className="boot-ping" />
            <Image
              src="/vistara-emblem.png"
              alt=""
              width={64}
              height={64}
              priority={variant === "full"}
            />
          </span>
          <span className="boot-word">
            <span className="boot-base">Vistara</span>
            <span
              className="boot-fill"
              style={
                determinate
                  ? { clipPath: `inset(${((1 - pct) * 100).toFixed(1)}% 0 0 0)` }
                  : undefined
              }
            >
              Vistara
            </span>
          </span>
        </span>

        <span className="boot-scan" />
        <span className="boot-corner tl" />
        <span className="boot-corner tr" />
        <span className="boot-corner bl" />
        <span className="boot-corner br" />
      </div>

      {variant === "full" && (
        <p className="boot-status">{STATUS_MESSAGES[statusIdx]}</p>
      )}

      <div className="boot-hair" aria-hidden="true">
        <i
          style={determinate ? { width: `${(pct * 100).toFixed(1)}%` } : undefined}
          className={cn(!determinate && "ind")}
        />
      </div>
    </div>
  );
}
