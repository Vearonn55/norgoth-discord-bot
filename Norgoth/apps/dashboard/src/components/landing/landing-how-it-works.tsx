"use client";

import { CContainer } from "@coreui/react";
import { LandingSection } from "@/components/landing/landing-section";
import type { LandingCopy } from "@/components/landing/landing-copy";

export function LandingHowItWorks({ copy }: { copy: LandingCopy }) {
  const steps = [
    { title: copy.howLoginTitle, body: copy.howLoginBody },
    { title: copy.howInstallTitle, body: copy.howInstallBody },
    { title: copy.howConfigureTitle, body: copy.howConfigureBody },
  ];

  return (
    <LandingSection
      id="how-it-works"
      className="border-top border-secondary-subtle"
    >
      <CContainer style={{ maxWidth: 1100 }}>
        <h2 className="h3 mb-2">{copy.howTitle}</h2>
        <p className="text-body-secondary mb-4" style={{ maxWidth: 720 }}>
          {copy.howLead}
        </p>
        <div className="row g-3">
          {steps.map((step, index) => (
            <div key={step.title} className="col-md-4">
              <div className="norgoth-section-card norgoth-section-card-primary norgoth-card-interactive h-100 p-3">
                <div className="norgoth-stepper-index mb-3">{index + 1}</div>
                <h3 className="h5">{step.title}</h3>
                <p className="mb-0 small text-body-secondary">{step.body}</p>
              </div>
            </div>
          ))}
        </div>
      </CContainer>
    </LandingSection>
  );
}
