"use client";

import type { CSSProperties, ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface AnimatedListItem {
  id: string;
  node: ReactNode;
}

/**
 * New items slide/blur in from the top on mount (staggered). Parents key by
 * item id so only fresh items animate.
 */
export function AnimatedList({
  items,
  className,
  staggerMs = 60,
}: {
  items: AnimatedListItem[];
  className?: string;
  staggerMs?: number;
}) {
  return (
    <div className={cn("grid gap-2", className)}>
      {items.map((item, i) => (
        <div
          key={item.id}
          className="alist-item"
          style={{ animationDelay: `${Math.min(i, 6) * staggerMs}ms` } as CSSProperties}
        >
          {item.node}
        </div>
      ))}
    </div>
  );
}
