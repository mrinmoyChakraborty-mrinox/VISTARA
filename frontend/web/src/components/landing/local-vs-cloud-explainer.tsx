import { ArrowRight, GitBranch } from "lucide-react";

import { AnimatedBeam } from "@/components/ui-fx/animated-beam";
import { Reveal } from "@/components/landing/reveal";
import { SpotlightCard } from "@/components/ui-fx/spotlight-card";

const NODES = [
  {
    stage: "Browser",
    runs: "Capture + local gate",
    leaves: "Nothing leaves the device",
  },
  {
    stage: "Backend",
    runs: "Sessions + memory storage",
    leaves: "Structured JSON only",
  },
  {
    stage: "Groq VLM",
    runs: "Qwen3.8-27B sees",
    leaves: "Selected frames only",
  },
  {
    stage: "Database",
    runs: "Scenes, objects, events",
    leaves: "No raw video, ever",
  },
  {
    stage: "Evidence",
    runs: "Authorized storage",
    leaves: "One JPEG, only to you",
  },
];

const TABLE: [string, string, string][] = [
  ["Camera capture + local change gate", "Your browser", "Nothing. Frames stay local until the gate triggers."],
  ["Frame upload", "Browser → backend", "Only gated, downscaled JPEG frames (~2 FPS max)."],
  ["Visual understanding (VLM)", "Groq cloud (Qwen3.8-27B)", "The selected context frames."],
  ["Memory storage", "Backend / database", "Structured scene/object/event JSON, not raw video."],
  ["Embeddings", "Client-side (Qwen3-Embedding-0.6B in a Web Worker)", "The 1024-dim vector only, never the frames."],
  ["Chat reasoning", "Groq cloud (GPT-OSS 20B)", "Your question plus retrieved memory text."],
  ["Evidence", "Authorized storage", "A single authorized JPEG on request."],
];

/**
 * Local-vs-cloud pipeline: an AnimatedBeam over SpotlightCard nodes (Browser
 * → Backend → Groq VLM → Database → Evidence, with client-side embedding as
 * a side branch), the frozen stage table, and the suggested copy verbatim.
 */
export function LocalVsCloudExplainer() {
  return (
    <div style={{ display: "grid", gap: 24 }}>
      <div className="head" style={{ marginBottom: 0 }}>
        <h2>Where your video goes.</h2>
        <p>
          The live camera preview and the change detection that decides when
          something interesting happens run entirely in your browser. Only a
          small number of downscaled frames are sent when a change is detected.
          Visual understanding and chat run in the cloud. Your memory text is
          turned into a search vector locally, in a Web Worker, and only the
          vector is uploaded. Evidence frames are stored and returned only to
          you.
        </p>
      </div>

      <Reveal className="panel" aria-label="Memory pipeline">
        <AnimatedBeam from={[24, 84]} to={[296, 84]} width={320} height={110} label="Pipeline: browser, backend, Groq VLM, database, evidence" />
        <div
          style={{
            display: "grid",
            gap: 10,
            gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            marginTop: 8,
          }}
        >
          {NODES.map((node) => (
            <SpotlightCard
              key={node.stage}
              className="rounded-2xl border border-line bg-bg p-4"
            >
              <b className="mono" style={{ color: "var(--acc)" }}>
                {node.stage.toUpperCase()}
              </b>
              <p style={{ fontSize: ".9rem", marginTop: 6 }}>{node.runs}</p>
              <p className="mono mute" style={{ marginTop: 4 }}>
                {node.leaves}
              </p>
            </SpotlightCard>
          ))}
        </div>
        <div
          style={{
            display: "flex",
            gap: 10,
            alignItems: "flex-start",
            marginTop: 10,
            borderRadius: 16,
            border: "1px dashed var(--line)",
            background: "var(--bg)",
            padding: 14,
          }}
        >
          <GitBranch size={16} aria-hidden="true" style={{ color: "var(--acc)", flex: "none", marginTop: 2 }} />
          <p style={{ fontSize: ".9rem" }}>
            <b>Side branch — client-side embedding.</b>{" "}
            <span className="mute">
              Qwen3-Embedding-0.6B runs in a Web Worker (WebGPU, WASM fallback)
              and only the 1024-dim vector is uploaded.
            </span>
          </p>
        </div>
      </Reveal>

      <div className="panel" style={{ display: "grid", gap: 4 }}>
        <b className="mono mute">STAGE BY STAGE</b>
        {TABLE.map(([stage, runs, leaves]) => (
          <div
            key={stage}
            style={{
              display: "grid",
              gap: 2,
              gridTemplateColumns: "1fr",
              padding: "10px 2px",
              borderBottom: "1px dashed var(--line)",
            }}
          >
            <p style={{ fontWeight: 500, fontSize: ".95rem" }}>{stage}</p>
            <p className="mono" style={{ color: "var(--acc)" }}>
              {runs}
            </p>
            <p className="mono mute">{leaves}</p>
          </div>
        ))}
        <a
          href="/cameras"
          className="mono"
          style={{
            marginTop: 8,
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            color: "var(--acc)",
          }}
        >
          See it running in the product
          <ArrowRight size={13} aria-hidden="true" />
        </a>
      </div>
    </div>
  );
}
