"use client";

import { CContainer } from "@coreui/react";
import { LandingSection } from "@/components/landing/landing-section";
import {
  splitItems,
  type LandingCopy,
} from "@/components/landing/landing-copy";

export function LandingFeatures({ copy }: { copy: LandingCopy }) {
  const categories = [
    { title: copy.featureCommunity, items: splitItems(copy.featureCommunityItems) },
    { title: copy.featureModeration, items: splitItems(copy.featureModerationItems) },
    {
      title: copy.featureCommunication,
      items: splitItems(copy.featureCommunicationItems),
    },
    { title: copy.featureSupport, items: splitItems(copy.featureSupportItems) },
    { title: copy.featureAutomation, items: splitItems(copy.featureAutomationItems) },
    { title: copy.featureOperations, items: splitItems(copy.featureOperationsItems) },
  ];

  return (
    <LandingSection id="features" className="border-top border-secondary-subtle">
      <CContainer style={{ maxWidth: 1100 }}>
        <h2 className="h3 mb-2">{copy.featuresTitle}</h2>
        <p className="text-body-secondary mb-4">{copy.featuresLead}</p>
        <div className="row g-3">
          {categories.map((category) => (
            <div key={category.title} className="col-md-6 col-lg-4">
              <div className="norgoth-section-card norgoth-section-card-secondary norgoth-card-interactive h-100 p-3">
                <h3
                  className="h6 text-uppercase mb-3"
                  style={{ letterSpacing: "0.06em" }}
                >
                  {category.title}
                </h3>
                <ul className="mb-0 ps-3 small">
                  {category.items.map((item) => (
                    <li key={item} className="mb-1">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>
      </CContainer>
    </LandingSection>
  );
}
