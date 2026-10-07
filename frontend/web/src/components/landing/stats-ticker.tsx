"use client";

import { useEffect, useRef, useState } from "react";

import { STATS } from "@/lib/landing-data";
import { useInView } from "@/hooks/use-motion";
import { cn } from "@/lib/utils";

function CountUp({ to, active }: { to: number; active: boolean }) {
  const [value, setValue] = useState(0);
  const started = useRef(false);

  useEffect(() => {
    if (!active || started.current) return;
    started.current = true;

    let raf = 0;
    let t0: number | null = null;
    const step = (t: number) => {
      t0 = t0 ?? t;
      const p = Math.min((t - t0) / 1400, 1);
      setValue(Math.round(to * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [active, to]);

  return <b data-to={to}>{value.toLocaleString()}</b>;
}

export function StatsTicker({ className }: { className?: string }) {
  const { ref, inView } = useInView<HTMLDivElement>(0.15);

  return (
    <div ref={ref} className={cn("stats rv", inView && "in", className)}>
      {STATS.map((stat) => (
        <div key={stat.label}>
          <CountUp to={stat.to} active={inView} />
          <span className="mute">{stat.label}</span>
        </div>
      ))}
    </div>
  );
}