"use client";

import type { ReactNode } from "react";

import { useInView } from "@/hooks/use-motion";
import { cn } from "@/lib/utils";

/** Blur + translateY fade-in on scroll (threshold 0.15, one-shot). */
export function BlurFade({
  children,
  className,
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const { ref, inView } = useInView<HTMLDivElement>(0.15);
  return (
    <div
      ref={ref}
      className={cn("rv", inView && "in", className)}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  );
}
