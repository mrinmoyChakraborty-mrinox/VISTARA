import { DESK_SPOTS } from "@/lib/landing-data";

export function placeTransform(t: number): string {
  const i = Math.min(Math.floor(t), 1);
  const f = t - i;
  const a = DESK_SPOTS[i];
  const b = DESK_SPOTS[i + 1];
  return `translate(${a[0] + (b[0] - a[0]) * f},${a[1] + (b[1] - a[1]) * f})`;
}

export function DeskScene({
  t = 0,
  boardId,
  className,
  instant = false,
}: {
  t?: number;
  boardId: string;
  className?: string;
  instant?: boolean;
}) {
  return (
    <svg
      viewBox="0 0 400 240"
      role="img"
      aria-label="Desk with an ESP32 board"
      className={className}
    >
      <rect width="400" height="240" fill="var(--desk)" />
      <rect x="0" y="190" width="400" height="50" fill="var(--line)" />
      <rect x="30" y="60" width="90" height="70" rx="6" fill="var(--soft)" />
      <rect x="18" y="130" width="114" height="8" rx="4" fill="var(--mute)" />
      <rect x="320" y="165" width="22" height="40" rx="5" fill="var(--acc)" />
      <g
        className="eg"
        id={boardId}
        transform={placeTransform(t)}
        style={instant ? { transition: "none" } : undefined}
      >
        <circle
          className="ring"
          cx="18"
          cy="12"
          r="14"
          fill="none"
          stroke="var(--acc)"
          strokeWidth="2"
        />
        <rect width="36" height="24" rx="4" fill="#2d6a4f" />
        <rect x="6" y="5" width="14" height="10" rx="2" fill="#95d5b2" />
        <circle cx="29" cy="18" r="2.5" fill="#f5efc6" />
      </g>
    </svg>
  );
}