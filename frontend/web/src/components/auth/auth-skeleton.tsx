import { VistaraMark } from "@/components/brand/vistara-mark";

/**
 * Styled loading skeleton matching the login card's final size, so the
 * prerendered page never flashes unstyled text.
 */
export function AuthFormSkeleton() {
  return (
    <div className="glass login in" aria-hidden="true" style={{ animationDelay: ".1s" }}>
      <div className="row">
        <span className="small logo" style={{ fontSize: "1rem" }}>
          <VistaraMark size={20} />
          Vistara
        </span>
      </div>
      <div className="skel" style={{ height: 40, width: "55%", borderRadius: 12, margin: "22px 0 8px" }} />
      <div className="skel" style={{ height: 14, width: "70%", marginBottom: 16 }} />
      <div className="skel" style={{ height: 48, borderRadius: 999, marginBottom: 10 }} />
      <div className="skel" style={{ height: 48, borderRadius: 999, marginBottom: 10 }} />
      <div className="skel" style={{ height: 38, width: 70, borderRadius: 999, marginLeft: "auto" }} />
    </div>
  );
}
