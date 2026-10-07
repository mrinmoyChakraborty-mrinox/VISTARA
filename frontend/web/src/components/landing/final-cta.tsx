import { BeamButton } from "@/components/ui-fx/beam-button";
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
        <BeamButton href="/signup">Start your first memory</BeamButton>
      </Reveal>
    </section>
  );
}