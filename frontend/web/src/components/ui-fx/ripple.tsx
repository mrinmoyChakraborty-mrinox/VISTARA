import type { CSSProperties } from "react";

/**
 * One-shot expanding ripple. Parents remount it (via key) to retrigger, e.g.
 * on every change_detected pulse.
 */
export function Ripple({
  size = 44,
  style,
}: {
  size?: number;
  style?: CSSProperties;
}) {
  return (
    <span
      aria-hidden="true"
      className="pring"
      style={{ ...style, width: size, height: size }}
    />
  );
}
