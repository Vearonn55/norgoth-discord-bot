import { LandingFeatureRow } from "@/components/landing/landing-feature-row";
import { LandingSection } from "@/components/landing/landing-section";
import type { LandingCopy } from "@/components/landing/landing-copy";
import { LANDING_SHOWCASE_IDS } from "@/components/landing/landing-feature-catalog";

export function LandingFeatureShowcase({ copy }: { copy: LandingCopy }) {
  return (
    <LandingSection id="features" className="border-top border-secondary-subtle">
      <div className="container" style={{ maxWidth: 1100 }}>
        <h2 className="h3 mb-2">{copy.featuresTitle}</h2>
        <p className="text-body-secondary mb-4">{copy.featuresLead}</p>
        {LANDING_SHOWCASE_IDS.map((id, index) => (
          <LandingFeatureRow key={id} id={id} copy={copy} index={index} />
        ))}
      </div>
    </LandingSection>
  );
}
