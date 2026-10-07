import type { CSSProperties, ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Rotating conic border wrapper (same --a spin as the landing beam card). */
export function BorderBeam({
  children,
  className,
  radius = 22,
  duration = 5,
}: {
  children: ReactNode;
  className?: string;
  radius?: number;
  duration?: number;
}) {
  return (
    <div
      className={cn("beam", className)}
      style={{ borderRadius: radius, animationDuration: `${duration}s` } as CSSProperties}
    >
      {children}
    </div>
  );
}
