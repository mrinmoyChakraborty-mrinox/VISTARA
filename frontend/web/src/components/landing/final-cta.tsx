import { ShimmerButton } from "@/components/ui-fx/shimmer-button";
import { Reveal } from "@/components/landing/reveal";

export function FinalCta() {
  return (
    <section>
      <Reveal className="final">
        <div className="pill" data-s={2} style={{ margin: 0 }}>
          <span className="dot" />
          Memory active
        </div>
        <h2>Ship the loop. Start remembering.</h2>
        <ShimmerButton href="/signup">Start your first memory</ShimmerButton>
      </Reveal>
    </section>
  );
}