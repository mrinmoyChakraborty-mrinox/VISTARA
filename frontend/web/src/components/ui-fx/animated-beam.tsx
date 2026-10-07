/**
 * SVG beam between two nodes with a travelling dash (reuses the dash
 * keyframes). Nodes pulse with the ring animation.
 */
export function AnimatedBeam({
  from,
  to,
  width = 320,
  height = 120,
  label,
}: {
  from: [number, number];
  to: [number, number];
  width?: number;
  height?: number;
  label?: string;
}) {
  const midX = (from[0] + to[0]) / 2;
  const d = `M ${from[0]} ${from[1]} Q ${midX} ${Math.min(from[1], to[1]) - 24} ${to[0]} ${to[1]}`;
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      role="img"
      aria-label={label ?? "Connection beam"}
    >
      <path d={d} className="abeam" />
      {[from, to].map(([x, y], i) => (
        <g key={i}>
          <circle cx={x} cy={y} r="9" fill="none" stroke="var(--acc)" strokeWidth="2" className="ring" />
          <circle cx={x} cy={y} r="4" fill="var(--acc)" />
        </g>
      ))}
    </svg>
  );
}
