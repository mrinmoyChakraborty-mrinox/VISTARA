import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Viewfinder corner brackets around any content (no background of its own). */
export function ViewfinderCorners({
  children,
  className,
}: {
  children?: ReactNode;
  className?: string;
}) {
  return <div className={cn("vf", className)}>{children}</div>;
}
