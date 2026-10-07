"use client";

import { useState } from "react";

import { OBJECTS } from "@/lib/landing-data";
import { Reveal } from "@/components/landing/reveal";
import { cn } from "@/lib/utils";

export function ObjectStory() {
  const [active, setActive] = useState(0);

  return (
    <Reveal className="panel story">
      <div className="tabs" style={{ margin: 0, alignSelf: "start" }}>
        {OBJECTS.map((object, i) => (
          <button
            key={object.label}
            type="button"
            className={cn(active === i && "on")}
            onClick={() => setActive(i)}
          >
            {object.label}
          </button>
        ))}
      </div>
      <div className="tl" key={active}>
        {OBJECTS[active].entries.map((entry, k) => (
          <div key={entry[0]} style={{ animationDelay: `${k * 0.2 + 0.2}s` }}>
            <b className="mono">{entry[0]}</b> — {entry[1]}
          </div>
        ))}
      </div>
    </Reveal>
  );
}