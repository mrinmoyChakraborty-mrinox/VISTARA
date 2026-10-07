"use client";

import { useEffect, useRef, useState } from "react";

import { DESK_SPOTS, HERO_NAMES } from "@/lib/landing-data";
import { DeskScene } from "@/components/landing/desk-scene";
import { ShimmerButton } from "@/components/ui-fx/shimmer-button";
import { usePrefersReducedMotion } from "@/hooks/use-motion";

export function Hero() {
  const reduce = usePrefersReducedMotion();
  const [status, setStatus] = useState(0);
  const [pos, setPos] = useState(0);
  const [instant, setInstant] = useState(false);
  const [label, setLabel] = useState<[string, string]>([
    DESK_SPOTS[0][2],
    DESK_SPOTS[0][3],
  ]);

  const hs = useRef(0);
  const heroPos = useRef(0);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (reduce) return;
    const id = setInterval(() => {
      if (hs.current === 0) {
        setStatus(1);
        const n = (heroPos.current + 1) % 3;
        heroPos.current = n;
        setPos(n);
        if (n === 0) {
          setInstant(true);
          if (resetTimer.current) clearTimeout(resetTimer.current);
          resetTimer.current = setTimeout(() => setInstant(false), 30);
        }
        hs.current = 1;
      } else if (hs.current === 1) {
        setStatus(2);
        setLabel([DESK_SPOTS[heroPos.current][2], DESK_SPOTS[heroPos.current][3]]);
        hs.current = 2;
      } else {
        setStatus(0);
        hs.current = 0;
      }
    }, 1800);
    return () => {
      clearInterval(id);
      if (resetTimer.current) clearTimeout(resetTimer.current);
    };
  }, [reduce]);

  return (
    <section className="hero">
      <div>
        <div className="pill" data-s={status}>
          <span className="dot" />
          <span>{HERO_NAMES[status]}</span>
        </div>
        <h1>
          Ask your camera <span className="hl">what happened.</span>
        </h1>
        <p className="lead">
          Vistara watches quietly, remembers what moves, and answers your
          questions with the exact frame as proof.
        </p>
        <div className="cta">
          <ShimmerButton href="#rewind">Try the live demo</ShimmerButton>
          <a className="btn" href="#how">
            See how it works
          </a>
        </div>
      </div>
      <div style={{ position: "relative" }}>
        <div className="float f1">📟 ESP32 moved</div>
        <div className="float f2">● Memory saved</div>
        <div className="cam">
          <div className="bar mono">
            <span>cam-01 · desk</span>
            <span id="clock">{label[1]}</span>
          </div>
          <div className="view">
            <DeskScene t={pos} boardId="e1" instant={instant} />
            <div className="scan" />
            <span className="tag">{label[0]}</span>
          </div>
        </div>
      </div>
    </section>
  );
}