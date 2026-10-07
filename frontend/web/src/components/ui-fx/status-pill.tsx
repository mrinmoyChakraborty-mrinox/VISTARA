import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

const DEFAULT_LABELS = [
  "Waiting for change",
  "Analyzing event",
  "Memory saved",
] as const;

/**
 * Memory-state pill with the landing's dot colors (mute / amber blink /
 * green). Margin is opt-out: the landing pill carries margin-bottom.
 */
export function StatusPill({
  state,
  text,
  className,
  style,
}: {
  state: 0 | 1 | 2;
  text?: string;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <span className={cn("pill", className)} data-s={state} style={style}>
      <span className="dot" aria-hidden="true" />
      <span>{text ?? DEFAULT_LABELS[state]}</span>
    </span>
  );
}
