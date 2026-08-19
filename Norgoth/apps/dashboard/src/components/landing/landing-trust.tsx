import { LandingSection } from "@/components/landing/landing-section";
import type { LandingCopy } from "@/components/landing/landing-copy";

export function LandingTrust({ copy }: { copy: LandingCopy }) {
  const items = [
    { title: copy.trustOauthTitle, body: copy.trustOauthBody },
    { title: copy.trustGuildTitle, body: copy.trustGuildBody },
    { title: copy.trustPermsTitle, body: copy.trustPermsBody },
    { title: copy.trustDurableTitle, body: copy.trustDurableBody },
  ];

  return (
    <LandingSection id="trust" className="border-top border-secondary-subtle">
      <div className="container" style={{ maxWidth: 1100 }}>
        <h2 className="h3 mb-4">{copy.trustTitle}</h2>
        <div className="row g-3">
          {items.map((item) => (
            <div key={item.title} className="col-md-6 col-lg-3">
              <div className="norgoth-section-card norgoth-section-card-secondary h-100 p-3">
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
