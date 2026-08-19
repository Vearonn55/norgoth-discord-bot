"use client";

import { useEffect, useState } from "react";
import type { LandingCopy } from "@/components/landing/landing-copy";
import { LandingFeatureCard } from "@/components/landing/landing-feature-card";
import { LANDING_FEATURE_IDS } from "@/components/landing/landing-feature-catalog";
import type { LandingFeatureId } from "@/components/landing/landing-feature-catalog";
import { LandingSection } from "@/components/landing/landing-section";

export function LandingFeatureCardGrid({ copy }: { copy: LandingCopy }) {
  const [openId, setOpenId] = useState<LandingFeatureId | null>(null);

  function onToggle(id: LandingFeatureId) {
    setOpenId((current) => (current === id ? null : id));
  }

  useEffect(() => {
    if (!openId) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpenId(null);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [openId]);

  return (
    <LandingSection className="border-top border-secondary-subtle">
      <div className="container" style={{ maxWidth: 1100 }}>
        <h2 className="h3 mb-2">{copy.cardsTitle}</h2>
        <p className="text-body-secondary mb-4">{copy.cardsLead}</p>
        <div className="norgoth-landing-cards">
          {LANDING_FEATURE_IDS.map((id) => (
            <LandingFeatureCard
              key={id}
              id={id}
              copy={copy}
              open={openId === id}
              onToggle={onToggle}
            />
          ))}
        </div>
      </div>
    </LandingSection>
  );
}
