import type { CSSProperties } from "react";

/**
 * Expanding pulse ring (same ring keyframes as the ESP32 board marker).
 * Remount (via key) to retrigger a one-shot pulse.
 */
export function PulseRing({
  size = 28,
  style,
  className,
}: {
  size?: number;
  style?: CSSProperties;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={["pring", className].filter(Boolean).join(" ")}
      style={{ ...style, width: size, height: size }}
    />
  );
}
