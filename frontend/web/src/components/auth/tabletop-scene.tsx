"use client";

import { useEffect, useRef } from "react";

/**
 * Fixed 3D tabletop: pillars, breathing dome, pearls, stones. Pointer
 * parallax translates layers by their data-d depth (4–18px); enabled only
 * with hover capability and no reduced-motion preference.
 */
export function TabletopScene() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const RM = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const hover = window.matchMedia("(hover: hover)").matches;
    if (RM || !hover) return;
    const layers = Array.from(el.querySelectorAll<HTMLElement>(".L"));
    const onMove = (e: PointerEvent) => {
      const x = e.clientX / window.innerWidth - 0.5;
      const y = e.clientY / window.innerHeight - 0.5;
      layers.forEach((l) => {
        const k = Number(l.dataset.d ?? 0);
        l.style.transform = `translate(${-x * k}px,${-y * k}px)`;
      });
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, []);

  return (
    <div ref={ref} className="scene" aria-hidden="true">
      <div className="L pillar" data-d="4" style={{ left: "6%" }} />
      <div className="L pillar" data-d="4" style={{ left: "78%" }} />
      <div className="L dome" data-d="8" />
      <div className="L sph s1" data-d="18" />
      <div className="L sph s2" data-d="14" />
      <div className="L sph s3" data-d="12" />
      <div className="L stone t1" data-d="16" />
      <div className="L stone t2" data-d="14" />
      <div className="L stone t3" data-d="16" />
    </div>
  );
}
