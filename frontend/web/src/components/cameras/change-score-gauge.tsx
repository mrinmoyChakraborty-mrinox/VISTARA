/** Animated radial gauge for the live change score (0..1). */
export function ChangeScoreGauge({ score }: { score: number | null }) {
  const clamped = Math.min(1, Math.max(0, score ?? 0));
  const radius = 40;
  const circumference = 2 * Math.PI * radius;

  return (
    <div
      role="img"
      aria-label={
        score === null
          ? "Change score: no samples yet"
          : `Change score: ${Math.round(clamped * 100)} percent`
      }
      style={{ display: "grid", justifyItems: "center", gap: 4 }}
    >
      <svg width="96" height="96" viewBox="0 0 96 96">
        <circle
          cx="48"
          cy="48"
          r={radius}
          fill="none"
          stroke="var(--line)"
          strokeWidth="8"
        />
        <circle
          cx="48"
          cy="48"
          r={radius}
          fill="none"
          stroke="var(--acc)"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - clamped)}
          transform="rotate(-90 48 48)"
          style={{ transition: "stroke-dashoffset .3s" }}
        />
      </svg>
      <span className="mono mute">
        {score === null ? "—" : `${Math.round(clamped * 100)}%`}
      </span>
    </div>
  );
}
