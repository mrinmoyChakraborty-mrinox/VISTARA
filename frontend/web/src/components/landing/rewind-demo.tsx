"use client";

import { useEffect, useState } from "react";

import {
  DESK_SPOTS,
  REWIND_QUESTIONS,
  type RewindQuestion,
} from "@/lib/landing-data";
import { DeskScene } from "@/components/landing/desk-scene";
import { Reveal } from "@/components/landing/reveal";
import { usePrefersReducedMotion } from "@/hooks/use-motion";
import { cn } from "@/lib/utils";

function Answer({ item, reduce }: { item: RewindQuestion; reduce: boolean }) {
  const [typed, setTyped] = useState("");
  const [showDots, setShowDots] = useState(true);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let n = 0;
    let timer: ReturnType<typeof setTimeout>;

    const type = () => {
      n += 1;
      setTyped(item.a.slice(0, n));
      if (n < item.a.length) {
        timer = setTimeout(type, reduce ? 0 : 18);
      } else {
        setDone(true);
      }
    };

    timer = setTimeout(
      () => {
        setShowDots(false);
        type();
      },
      reduce ? 0 : 900,
    );

    return () => clearTimeout(timer);
  }, [item, reduce]);

  return (
    <>
      <div className="msg q">{item.q}</div>
      <div className="msg a">
        {showDots ? (
          <span className="dots">
            <span />
            <span />
            <span />
          </span>
        ) : (
          typed
        )}
      </div>
      {done && (
        <div className="ev">
          <div />
          <span className="mono">
            {item.frame}
            <br />
            <span className="mute">open evidence</span>
          </span>
        </div>
      )}
    </>
  );
}

export function RewindDemo() {
  const reduce = usePrefersReducedMotion();
  const [value, setValue] = useState(0);
  const [qi, setQi] = useState<number | null>(null);

  const t = value / 100;
  const spot = DESK_SPOTS[Math.round(t)];

  return (
    <section id="rewind">
      <Reveal className="head">
        <h2>Drag time. Watch it move.</h2>
        <p>
          Scrub the timeline, then ask a question. Everything here runs on
          sample data.
        </p>
      </Reveal>
      <Reveal className="rw">
        <div className="panel">
          <div className="view">
            <DeskScene t={t} boardId="e2" />
            <span className="tag">
              {spot[3]} — {spot[2]}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={200}
            value={value}
            aria-label="Timeline"
            onChange={(e) => setValue(Number(e.target.value))}
          />
          <div className="ticks mono mute">
            <span>10:41</span>
            <span>10:43</span>
            <span>10:47</span>
          </div>
        </div>
        <div className="panel">
          <div className="chips">
            {REWIND_QUESTIONS.map((item, i) => (
              <button
                key={item.q}
                type="button"
                className={cn("q", qi === i && "on")}
                onClick={() => setQi(i)}
              >
                {item.q}
              </button>
            ))}
          </div>
          <div className="chat">
            {qi === null ? (
              <p className="mute">Pick a question to ask the memory.</p>
            ) : (
              <Answer key={qi} item={REWIND_QUESTIONS[qi]} reduce={reduce} />
            )}
          </div>
        </div>
      </Reveal>
    </section>
  );
}