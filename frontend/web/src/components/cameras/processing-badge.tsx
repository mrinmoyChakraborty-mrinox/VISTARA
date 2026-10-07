const STAGES: { stage: string; place: string; local: boolean }[] = [
  { stage: "Capture + local change gate", place: "Your browser", local: true },
  { stage: "Frame upload (gated JPEGs)", place: "Browser → backend", local: true },
  { stage: "Visual understanding", place: "Groq cloud · Qwen3.8-27B", local: false },
  { stage: "Memory storage", place: "Backend database", local: false },
  { stage: "Embeddings", place: "Client worker · Qwen3-Embedding", local: true },
  { stage: "Chat reasoning", place: "Groq cloud · GPT-OSS 20B", local: false },
  { stage: "Evidence", place: "Authorized storage", local: false },
];

/** Compact local-vs-cloud explainer: where video goes, and what never does. */
export function ProcessingBadge() {
  return (
    <section
      aria-label="Where your video goes"
      className="panel proc-badge"
      style={{ display: "grid", gap: 4 }}
    >
      <b className="mono mute">WHERE YOUR VIDEO GOES</b>
      {STAGES.map((row) => (
        <div
          key={row.stage}
          className="mono"
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            gap: 12,
            padding: "6px 2px",
            borderBottom: "1px dashed var(--line)",
          }}
        >
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <span
              className={`sdot ${row.local ? "green" : "blue"}`}
              aria-hidden="true"
            />
            {row.stage}
          </span>
          <span className="mute" style={{ textAlign: "right" }}>
            {row.place}
          </span>
        </div>
      ))}
      <p className="mute" style={{ fontSize: ".85rem", marginTop: 8 }}>
        The preview and the gate run entirely in your browser. Only gated,
        downscaled frames are sent — and only the vector from your device is
        ever uploaded for search.
      </p>
    </section>
  );
}
