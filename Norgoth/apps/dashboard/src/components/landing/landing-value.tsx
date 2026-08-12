"use client";

import { CContainer } from "@coreui/react";
import { LandingSection } from "@/components/landing/landing-section";
import type { LandingCopy } from "@/components/landing/landing-copy";

export function LandingValue({ copy }: { copy: LandingCopy }) {
  const cards = [
    { title: copy.valueFewerBotsTitle, body: copy.valueFewerBotsBody },
    {
      title: copy.valueFewerDashboardsTitle,
      body: copy.valueFewerDashboardsBody,
    },
    {
      title: copy.valueLessFragmentationTitle,
      body: copy.valueLessFragmentationBody,
    },
  ];

  return (
    <LandingSection className="border-top border-secondary-subtle">
      <CContainer style={{ maxWidth: 1100 }}>
        <h2 className="h3 mb-2">{copy.valueTitle}</h2>
        <p className="text-body-secondary mb-4" style={{ maxWidth: 720 }}>
          {copy.valueLead}
        </p>
        <div className="row g-3">
          {cards.map((item) => (
            <div key={item.title} className="col-md-4">
              <div className="norgoth-section-card norgoth-section-card-primary norgoth-card-interactive h-100 p-3">
                <h3 className="h5">{item.title}</h3>
                <p className="mb-0 small text-body-secondary">{item.body}</p>
              </div>
            </div>
          ))}
        </div>
      </CContainer>
    </LandingSection>
  );
}
