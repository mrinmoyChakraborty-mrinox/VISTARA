"use client";

import { useEffect, useRef, useState } from "react";

import { useInView, usePrefersReducedMotion } from "@/hooks/use-motion";

/** Count-up ticker that starts when scrolled into view. RM-safe: jumps to final. */
export function NumberTicker({
  value,
  decimals = 0,
  duration = 1400,
  className,
}: {
  value: number;
  decimals?: number;
  duration?: number;
  className?: string;
}) {
  const { ref, inView } = useInView<HTMLSpanElement>(0.15);
  const reduce = usePrefersReducedMotion();
  const [display, setDisplay] = useState(0);
  const started = useRef(false);

  useEffect(() => {
    if (!inView || started.current) return;
    started.current = true;
    if (reduce) {
      const id = requestAnimationFrame(() => setDisplay(value));
      return () => cancelAnimationFrame(id);
    }
    let raf = 0;
    let t0: number | null = null;
    const step = (t: number) => {
      t0 = t0 ?? t;
      const p = Math.min((t - t0) / duration, 1);
      setDisplay(value * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [inView, value, duration, reduce]);

  const text =
    decimals > 0
      ? display.toFixed(decimals)
      : Math.round(display).toLocaleString();

  return (
    <span ref={ref} className={className}>
      {text}
    </span>
  );
}
