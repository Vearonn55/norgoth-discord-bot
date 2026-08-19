import { LandingSection } from "@/components/landing/landing-section";
import type { LandingCopy } from "@/components/landing/landing-copy";

export function LandingWhy({ copy }: { copy: LandingCopy }) {
  const items = [
    { title: copy.whyModularTitle, body: copy.whyModularBody },
    { title: copy.whyDiscordTitle, body: copy.whyDiscordBody },
    { title: copy.whyDurableTitle, body: copy.whyDurableBody },
  ];

  return (
    <LandingSection id="why" className="border-top border-secondary-subtle">
      <div className="container" style={{ maxWidth: 1100 }}>
        <h2 className="h3 mb-2">{copy.whyTitle}</h2>
        <p className="text-body-secondary mb-4" style={{ maxWidth: 720 }}>
          {copy.whyLead}
        </p>
        <div className="row g-3">
          {items.map((item) => (
            <div key={item.title} className="col-md-4">
              <div className="norgoth-section-card norgoth-section-card-primary h-100 p-3">
                <h3 className="h5">{item.title}</h3>
                <p className="mb-0 small text-body-secondary">{item.body}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </LandingSection>
  );
}
