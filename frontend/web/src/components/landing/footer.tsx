import { VistaraMark } from "@/components/brand/vistara-mark";

export function Footer() {
  return (
    <footer
      className="mono mute"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 10,
      }}
    >
      <VistaraMark size={24} />
      <span>Vistara · open-source visual memory · built in a day</span>
    </footer>
  );
}