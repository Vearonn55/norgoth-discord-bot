"use client";

import { useEffect, useState } from "react";
import type { LandingCopy } from "@/components/landing/landing-copy";
import { LandingFeatureCard } from "@/components/landing/landing-feature-card";
import { LANDING_FEATURE_IDS } from "@/components/landing/landing-feature-catalog";
import type { LandingFeatureId } from "@/components/landing/landing-feature-catalog";
import { LandingSection } from "@/components/landing/landing-section";

export function LandingFeatureCardGrid({
  copy,
  sidebar,
}: {
  copy: LandingCopy;
  sidebar: Record<string, string>;
}) {
  const [openId, setOpenId] = useState<LandingFeatureId | null>(null);

  function onOpen(id: LandingFeatureId) {
    setOpenId(id);
  }

  function onClose(id: LandingFeatureId) {
    setOpenId((current) => (current === id ? null : current));
  }

  function onToggle(id: LandingFeatureId) {
    setOpenId((current) => (current === id ? null : id));
  }

  useEffect(() => {
    if (openId === null) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpenId(null);
      }
    }

    function onPointerDown(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const card = target.closest("[data-feature-id]");
      if (!card || card.getAttribute("data-feature-id") !== openId) {
        setOpenId(null);
      }
    }

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
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
              sidebar={sidebar}
              open={openId === id}
              onOpen={onOpen}
              onClose={onClose}
              onToggle={onToggle}
            />
          ))}
        </div>
      </div>
    </LandingSection>
  );
}
