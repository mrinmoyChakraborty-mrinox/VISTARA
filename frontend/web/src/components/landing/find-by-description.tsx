"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { FIND_DATASETS } from "@/lib/landing-data";
import { Reveal } from "@/components/landing/reveal";
import { ShimmerButtonBase } from "@/components/ui-fx/shimmer-button";
import { usePrefersReducedMotion } from "@/hooks/use-motion";
import { cn } from "@/lib/utils";

type Hit = { id: number; x: number; y: number; on: boolean };
type LogRow = { time: string; place: string; cam: string; conf: number };
type Timers = ReturnType<typeof setTimeout>[];

export function FindByDescription() {
  const reduce = usePrefersReducedMotion();
  const [mode, setMode] = useState(0);
  const [text, setText] = useState(FIND_DATASETS[0].text);
  const [status, setStatus] = useState("Ready. Sample footage memory loaded.");
  const [scanning, setScanning] = useState(false);
  const [scanKey, setScanKey] = useState(0);
  const [hits, setHits] = useState<Hit[]>([]);
  const [rows, setRows] = useState<LogRow[]>([]);
  const [points, setPoints] = useState("");
  const timers = useRef<Timers>([]);

  const clearTimers = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  const reset = useCallback(() => {
    clearTimers();
    setHits([]);
    setRows([]);
    setPoints("");
    setScanning(false);
    setStatus("Ready. Sample footage memory loaded.");
  }, [clearTimers]);

  const selectMode = (nextMode: number) => {
    setMode(nextMode);
    setText(FIND_DATASETS[nextMode].text);
    reset();
  };

  const search = () => {
    reset();
    setScanning(true);
    setScanKey((k) => k + 1);
    setStatus("Scanning 5 cameras · 38 hours of memory...");

    const data = FIND_DATASETS[mode].hits;
    let i = 0;
    const acc: string[] = [];

    const next = () => {
      if (i >= data.length) {
        setStatus(
          `${data.length} sightings found. No time or place was needed.`,
        );
        return;
      }
      const hit = data[i];
      acc.push(hit[4].join(","));
      setPoints(acc.join(" "));
      const id = i;
      setRows((prev) => [
        ...prev,
        { time: hit[0], place: hit[1], cam: hit[2], conf: hit[3] },
      ]);
      setHits((prev) => [
        ...prev,
        { id, x: hit[4][0], y: hit[4][1], on: false },
      ]);
      timers.current.push(
        setTimeout(() => {
          setHits((prev) =>
            prev.map((h) => (h.id === id ? { ...h, on: true } : h)),
          );
        }, 30),
      );
      i += 1;
      timers.current.push(setTimeout(next, reduce ? 0 : 550));
    };

    timers.current.push(setTimeout(next, reduce ? 0 : 1300));
  };

  return (
    <section id="vision">
      <Reveal className="head">
        <span className="soon">Coming next · CCTV memory</span>
        <h2>Describe it. Vistara finds every sighting.</h2>
        <p>
          Lost bag, missing tool, or a person you need to locate? Type what it
          looks like. No time window, no camera to pick, no place to guess.
        </p>
      </Reveal>
      <Reveal className="fd">
        <div className="panel">
          <div className="seg" data-m={mode}>
            <i />
            <button
              type="button"
              className={cn(mode === 0 && "on")}
              onClick={() => selectMode(0)}
            >
              Object
            </button>
            <button
              type="button"
              className={cn(mode === 1 && "on")}
              onClick={() => selectMode(1)}
            >
              Person
            </button>
          </div>
          <textarea
            aria-label="Describe what to find"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="hint mono">
            <span>time</span>
            <span>place</span>
            <span>camera</span>
          </div>
          <ShimmerButtonBase
            id="srch"
            type="button"
            onClick={search}
          >
            Search all footage
          </ShimmerButtonBase>
          <div className={cn("sbar", scanning && "go")} key={scanKey}>
            <b />
          </div>
          <p className="mono mute">{status}</p>
        </div>
        <div className="panel">
          <svg
            className="map"
            viewBox="0 0 320 200"
            role="img"
            aria-label="Site map with camera sightings"
          >
            <rect className="room" x="10" y="10" width="120" height="80" rx="8" />
            <text x="18" y="24">
              Main entrance
            </text>
            <rect className="room" x="140" y="10" width="170" height="80" rx="8" />
            <text x="148" y="24">
              Lobby
            </text>
            <rect className="room" x="10" y="98" width="300" height="32" rx="8" />
            <text x="18" y="112">
              Corridor B
            </text>
            <rect className="room" x="10" y="138" width="150" height="52" rx="8" />
            <text x="18" y="152">
              Parking lot
            </text>
            <rect className="room" x="170" y="138" width="140" height="52" rx="8" />
            <text x="178" y="152">
              Back exit
            </text>
            <polyline points={points} />
            <g>
              {hits.map((hit) => (
                <g className={cn("hit", hit.on && "on")} key={hit.id}>
                  <circle
                    cx={hit.x}
                    cy={hit.y}
                    r="9"
                    fill="none"
                    stroke="var(--acc)"
                    strokeWidth="2"
                  />
                  <circle cx={hit.x} cy={hit.y} r="5" fill="var(--acc)" />
                </g>
              ))}
            </g>
          </svg>
          <div className="log">
            {rows.length === 0 ? (
              <p className="mute">
                Sightings will appear here with time and place.
              </p>
            ) : (
              rows.map((row, i) => (
                <div className="row" key={i}>
                  <b className="mono">{row.time}</b>
                  <span>
                    {row.place}
                    <small>{row.cam} · evidence frame</small>
                  </span>
                  <span className="conf">{row.conf}%</span>
                </div>
              ))
            )}
          </div>
        </div>
      </Reveal>
    </section>
  );
}