"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function ordinal(day: number): string {
  if (day >= 11 && day <= 13) return `${day}th`;
  switch (day % 10) {
    case 1:
      return `${day}st`;
    case 2:
      return `${day}nd`;
    case 3:
      return `${day}rd`;
    default:
      return `${day}th`;
  }
}

/**
 * Tall ivory card: live date, gradient orbs, ESP32 pulse marker, memory
 * status, and a Watch demo pill. Tilts in 3D toward the cursor.
 */
export function DateCard({ variant }: { variant: "login" | "signup" }) {
  const [now, setNow] = useState<Date | null>(null);
  const card = useRef<HTMLDivElement>(null);
  const live = useRef(false);

  useEffect(() => {
    const frame = requestAnimationFrame(() => setNow(new Date()));
    const RM = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const hover = window.matchMedia("(hover: hover)").matches;
    live.current = !RM && hover;
    return () => cancelAnimationFrame(frame);
  }, []);

  const onMove = (e: React.PointerEvent) => {
    const el = card.current;
    if (!el || !live.current) return;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `perspective(900px) rotateY(${x * 8}deg) rotateX(${-y * 8}deg)`;
  };

  const onLeave = () => {
    if (card.current) card.current.style.transform = "";
  };

  return (
    <div
      ref={card}
      className="rc in"
      style={{ animationDelay: ".34s" }}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
    >
      <div className="orb2" />
      <div className="orb" />
      <div className="mk" />
      <div className="tr">
        <span className="dotg" />
        Memory saved
        <br />
        Evidence attached
      </div>
      <div className="inset">
        <div>
          <div className="day">
            {now ? WEEKDAYS[now.getDay()] : "···"}
            <span>{now ? ordinal(now.getDate()) : "···"}</span>
          </div>
        </div>
        <div className="meta">
          10:43 · Desk camera
          <br />
          {variant === "login" ? (
            <>
              ESP32 moved:<br />
              beside laptop
            </>
          ) : (
            <>
              First memory in:<br />2 minutes
            </>
          )}
        </div>
        <div style={{ height: 44 }} />
      </div>
      <div className="rb">
        <span className="logo">
          <b />
          Vistara
        </span>
        <Link className="pillb" href="/#rewind">
          Watch demo <i>→</i>
        </Link>
      </div>
    </div>
  );
}
