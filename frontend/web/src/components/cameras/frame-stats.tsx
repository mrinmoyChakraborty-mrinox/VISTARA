/** Live sampler stats: send rate and average frame weight. */
export function FrameStats({
  fps,
  kbPerFrame,
  sent,
}: {
  fps: number;
  kbPerFrame: number;
  sent: number;
}) {
  return (
    <dl
      className="mono mute"
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, auto)",
        gap: 16,
        justifyContent: "start",
        margin: 0,
      }}
    >
      <div>
        <dt style={{ opacity: 0.7 }}>FPS sent</dt>
        <dd style={{ margin: 0, color: "var(--ink)", fontSize: "1rem" }}>
          {fps.toFixed(1)}
        </dd>
      </div>
      <div>
        <dt style={{ opacity: 0.7 }}>KB / frame</dt>
        <dd style={{ margin: 0, color: "var(--ink)", fontSize: "1rem" }}>
          {kbPerFrame.toFixed(1)}
        </dd>
      </div>
      <div>
        <dt style={{ opacity: 0.7 }}>Frames sent</dt>
        <dd style={{ margin: 0, color: "var(--ink)", fontSize: "1rem" }}>
          {sent.toLocaleString()}
        </dd>
      </div>
    </dl>
  );
}
