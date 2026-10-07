"use client";

import { useRef, type ReactNode, type MouseEvent } from "react";

import { cn } from "@/lib/utils";

/** Cursor-follow spotlight wrapper. Sets --mx/--my; the glow is pure CSS. */
export function SpotlightCard({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);

  const onMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - rect.left}px`);
    el.style.setProperty("--my", `${e.clientY - rect.top}px`);
  };

  return (
    <div ref={ref} onMouseMove={onMouseMove} className={cn("spot", className)}>
      {children}
    </div>
  );
}
