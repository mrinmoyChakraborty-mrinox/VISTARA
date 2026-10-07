import { AuroraBackground } from "@/components/landing/aurora-background";
import { LandingNav } from "@/components/landing/landing-nav";
import { Hero } from "@/components/landing/hero";
import { PillMarquee } from "@/components/landing/pill-marquee";
import { HowItWorks } from "@/components/landing/how-it-works";
import { RewindDemo } from "@/components/landing/rewind-demo";
import { FeatureBento } from "@/components/landing/feature-bento";
import { LocalVsCloudExplainer } from "@/components/landing/local-vs-cloud-explainer";
import { StatsTicker } from "@/components/landing/stats-ticker";
import { ObjectStory } from "@/components/landing/object-story";
import { FindByDescription } from "@/components/landing/find-by-description";
import { FinalCta } from "@/components/landing/final-cta";
import { Footer } from "@/components/landing/footer";
import { Reveal } from "@/components/landing/reveal";

export default function Home() {
  return (
    <>
      <AuroraBackground />
      <LandingNav />
      <main id="top" className="wrap">
        <Hero />
        <PillMarquee />
        <HowItWorks />
        <RewindDemo />
        <section id="features">
          <Reveal className="head">
            <h2>Built to remember, honest about what it knows.</h2>
          </Reveal>
          <FeatureBento />
          <div id="privacy" style={{ marginTop: 72, scrollMarginTop: 90 }}>
            <LocalVsCloudExplainer />
          </div>
          <StatsTicker />
        </section>
        <section>
          <Reveal className="head">
            <h2>Follow one object through time.</h2>
          </Reveal>
          <ObjectStory />
        </section>
        <FindByDescription />
        <FinalCta />
      </main>
      <Footer />
    </>
  );
}