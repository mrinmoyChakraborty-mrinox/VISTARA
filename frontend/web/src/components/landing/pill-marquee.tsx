import { MARQUEE_ITEMS, type MarqueeItem } from "@/lib/landing-data";
import { Reveal } from "@/components/landing/reveal";

function Chip({ item }: { item: MarqueeItem }) {
  return (
    <div className="chip">
      <i style={{ "--c": item.color } as React.CSSProperties}>{item.icon}</i>
      <span>
        {item.name} <small>last seen {item.time}</small>
      </span>
    </div>
  );
}

export function PillMarquee() {
  const rows = [0, 1, 2, 3].map((r) =>
    MARQUEE_ITEMS.slice(r * 2).concat(MARQUEE_ITEMS.slice(0, r * 2)),
  );

  return (
    <Reveal className="mq" aria-label="Things Vistara remembers" id="mq">
      {rows.map((row, r) => (
        <div className="track" key={r}>
          {[0, 1].map((k) =>
            row.map((item, idx) => <Chip key={`${r}-${k}-${idx}`} item={item} />),
          )}
        </div>
      ))}
    </Reveal>
  );
}