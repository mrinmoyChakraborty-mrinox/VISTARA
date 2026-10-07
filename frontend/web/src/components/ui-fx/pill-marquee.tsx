import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

export interface PillMarqueeItem {
  icon: string;
  label: string;
  sub?: string;
  color: string;
}

/** Generic offset-row pill marquee with fading edges and hover pause. */
export function PillMarquee({
  items,
  rows = 4,
  label,
  className,
  duration = 38,
}: {
  items: PillMarqueeItem[];
  rows?: number;
  label?: string;
  className?: string;
  duration?: number;
}) {
  const tracks = Array.from({ length: rows }, (_, r) =>
    items.slice(r * 2).concat(items.slice(0, r * 2)),
  );

  return (
    <div className={cn("mq", className)} aria-label={label}>
      {tracks.map((row, r) => (
        <div
          key={r}
          className="track"
          style={{ animationDuration: `${duration}s` } as CSSProperties}
        >
          {[0, 1].map((k) =>
            row.map((item, idx) => (
              <div className="chip" key={`${r}-${k}-${idx}`}>
                <i style={{ "--c": item.color } as CSSProperties}>
                  {item.icon}
                </i>
                <span>
                  {item.label}{" "}
                  {item.sub ? <small>{item.sub}</small> : null}
                </span>
              </div>
            )),
          )}
        </div>
      ))}
    </div>
  );
}
