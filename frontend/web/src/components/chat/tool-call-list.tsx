"use client";

import { useState } from "react";
import { ChevronDown, Wrench } from "lucide-react";

import type { ToolResult } from "@/types/domain";
import { cn } from "@/lib/utils";

const KNOWN_TOOLS = [
  "search_memory",
  "get_object_history",
  "get_last_seen",
  "get_events",
  "get_scene",
  "get_memory",
  "get_evidence",
];

/** Collapsible, tool-grouped diagnostic trail. Display only — never invoked. */
export function ToolCallList({ calls }: { calls: ToolResult[] }) {
  const [open, setOpen] = useState(false);

  const groups = new Map<string, ToolResult[]>();
  for (const call of calls) {
    const list = groups.get(call.tool) ?? [];
    list.push(call);
    groups.set(call.tool, list);
  }
  const ordered = [...groups.entries()].sort(([a], [b]) => {
    const ai = KNOWN_TOOLS.indexOf(a);
    const bi = KNOWN_TOOLS.indexOf(b);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  return (
    <div
      style={{
        borderRadius: 12,
        border: "1px solid var(--line)",
        background: "var(--bg)",
        marginTop: 8,
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="mono mute"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          width: "100%",
          padding: "8px 12px",
          background: "none",
          border: 0,
          cursor: "pointer",
          font: "inherit",
        }}
      >
        <Wrench size={13} aria-hidden="true" />
        {calls.length} tool call{calls.length === 1 ? "" : "s"}
        <ChevronDown
          size={14}
          aria-hidden="true"
          style={{
            marginLeft: "auto",
            transition: "transform .25s",
            transform: open ? "rotate(180deg)" : "none",
          }}
        />
      </button>
      <div className={cn(!open && "hidden")} style={{ padding: "0 12px 12px", display: "grid", gap: 10 }}>
        {ordered.map(([tool, list]) => (
          <div key={tool}>
            <p className="mono" style={{ color: "var(--acc)" }}>
              {tool} × {list.length}
            </p>
            {list.map((call, i) => (
              <pre
                key={i}
                className="mono mute"
                style={{
                  margin: "6px 0 0",
                  padding: 8,
                  borderRadius: 8,
                  background: "color-mix(in srgb, var(--line) 45%, transparent)",
                  overflowX: "auto",
                  fontSize: ".72rem",
                }}
              >
                {JSON.stringify({ args: call.args, result: call.result }, null, 1)}
              </pre>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
