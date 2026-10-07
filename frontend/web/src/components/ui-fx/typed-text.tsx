"use client";

import { useEffect, useState } from "react";

import { usePrefersReducedMotion } from "@/hooks/use-motion";

/**
 * Progressive character reveal. Reveal-only: the finished text always equals
 * the source string verbatim.
 */
function Typer({
  text,
  speed,
  startDelay,
  className,
}: {
  text: string;
  speed: number;
  startDelay: number;
  className?: string;
}) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let n = 0;
    let timer: ReturnType<typeof setTimeout>;
    const type = () => {
      n += 1;
      setCount(n);
      if (n < text.length) timer = setTimeout(type, speed);
    };
    timer = setTimeout(type, startDelay);
    return () => clearTimeout(timer);
  }, [text, speed, startDelay]);

  return <span className={className}>{text.slice(0, count)}</span>;
}

export function TypedText({
  text,
  speed = 18,
  startDelay = 500,
  className,
}: {
  text: string;
  speed?: number;
  startDelay?: number;
  className?: string;
}) {
  const reduce = usePrefersReducedMotion();
  // Reduced motion (and the finished state) shows the answer verbatim.
  if (reduce) return <span className={className}>{text}</span>;
  // Keyed by text so a new answer always types from the start.
  return <Typer key={text} text={text} speed={speed} startDelay={startDelay} className={className} />;
}
