"use client";

import { useRef, useState } from "react";

import { FEATURES, FEATURE_TABS, type FeatureCategory } from "@/lib/landing-data";
import { Reveal } from "@/components/landing/reveal";
import { cn } from "@/lib/utils";

export function FeatureBento() {
  const [filter, setFilter] = useState<FeatureCategory>("all");

  return (
    <>
      <Reveal className="tabs">
        {FEATURE_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={cn(filter === tab.key && "on")}
            onClick={() => setFilter(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </Reveal>
      <Reveal className="bento">
        {FEATURES.map((feature, i) => (
          <FeatureCard
            key={i}
            feature={feature}
            hidden={filter !== "all" && feature.category !== filter}
          />
        ))}
      </Reveal>
    </>
  );
}

function FeatureCard({
  feature,
  hidden,
}: {
  feature: (typeof FEATURES)[number];
  hidden: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);

  const onMouseMove = (e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - r.left}px`);
    el.style.setProperty("--my", `${e.clientY - r.top}px`);
  };

  return (
    <div
      ref={ref}
      className={cn("fc", feature.wide && "wide", hidden && "hide")}
      onMouseMove={onMouseMove}
    >
      <span className="ic">{feature.icon}</span>
      <h3>{feature.title}</h3>
      <p>{feature.body}</p>
    </div>
  );
}