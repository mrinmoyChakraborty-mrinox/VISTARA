"use client";

import { useEffect, useRef, useState } from "react";

import { STEPS } from "@/lib/landing-data";
import { Reveal } from "@/components/landing/reveal";
import { usePrefersReducedMotion } from "@/hooks/use-motion";
import { cn } from "@/lib/utils";

const CELL_COUNT = 32;

export function HowItWorks() {
  const reduce = usePrefersReducedMotion();
  const [cur, setCur] = useState(0);
  const [paused, setPaused] = useState(false);
  const [hot, setHot] = useState<number[]>([]);
  const [caption, setCaption] = useState("no change · skipping AI");
  const curRef = useRef(0);

  useEffect(() => {
    curRef.current = cur;
  }, [cur]);

  useEffect(() => {
    if (reduce || paused) return;
    const id = setTimeout(() => {
      setCur((c) => (c + 1) % STEPS.length);
    }, 5000);
    return () => clearTimeout(id);
  }, [cur, reduce, paused]);

  useEffect(() => {
    if (reduce) return;
    const id = setInterval(() => {
      if (curRef.current !== 1) return;
      const busy = Math.random() > 0.45;
      if (busy) {
        const s = Math.floor(Math.random() * 26);
        setHot([s, s + 1, s + 8, s + 9].filter((n) => n < CELL_COUNT));
      } else {
        setHot([]);
      }
      setCaption(
        busy ? "change found · sending 4 frames" : "no change · skipping AI",
      );
    }, 900);
    return () => clearInterval(id);
  }, [reduce]);

  return (
    <section id="how">
      <Reveal className="head">
        <h2>Watch, notice, remember, ask.</h2>
        <p>Four steps, one loop. Pick a step or let it play.</p>
      </Reveal>
      <Reveal className="steps">
        <div className="stp">
          {STEPS.map((step, i) => (
            <button
              key={step.title}
              type="button"
              className={cn("st", cur === i && "on")}
              onClick={() => {
                setCur(i);
                setPaused(false);
              }}
              onMouseEnter={() => setPaused(true)}
              onMouseLeave={() => setPaused(false)}
            >
              <h3>{step.title}</h3>
              <p>{step.body}</p>
              <span className="pg" key={cur === i ? `on-${i}` : `off-${i}`} />
            </button>
          ))}
        </div>
        <div className="stage">
          <div className={cn("pane", cur === 0 && "on")}>
            <div className="view" style={{ width: "100%" }}>
              <div className="scan" />
              <span className="tag">cam-01 · 2 fps</span>
              <svg viewBox="0 0 400 240">
                <rect width="400" height="240" fill="var(--desk)" />
                <rect x="30" y="60" width="90" height="70" rx="6" fill="var(--soft)" />
                <rect x="320" y="170" width="22" height="40" rx="4" fill="var(--acc)" />
              </svg>
            </div>
          </div>
          <div className={cn("pane", cur === 1 && "on")}>
            <div style={{ width: "100%", textAlign: "center" }}>
              <div className="grid" style={{ margin: "0 auto 14px" }}>
                {Array.from({ length: CELL_COUNT }, (_, i) => (
                  <b key={i} className={hot.includes(i) ? "hot" : undefined} />
                ))}
              </div>
              <p className="mono mute">{caption}</p>
            </div>
          </div>
          <div className={cn("pane", cur === 2 && "on")}>
            <div className="mem">
              <span className="stamp">SAVED</span>
              <div className="frames">
                <div />
                <div />
                <div />
              </div>
              <b className="mono">10:43 — beside laptop</b>
              <p className="mute" style={{ fontSize: ".88rem" }}>
                ESP32 moved from center of desk. Evidence attached.
              </p>
            </div>
          </div>
          <div className={cn("pane", cur === 3 && "on")}>
            <div style={{ width: "100%" }}>
              <div className="msg q">Where was the ESP32 before I moved it?</div>
              <div className="msg a">
                It was at the center of the desk until 10:43, then moved beside
                the laptop.
              </div>
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}