"use client";

import { useEffect, useState } from "react";
import { AnimatePresence } from "motion/react";
import type { LandingCopy } from "@/components/landing/landing-copy";
import {
  LANDING_FEATURE_DETAIL_ID,
  LandingFeatureCard,
} from "@/components/landing/landing-feature-card";
import { LANDING_FEATURE_IDS } from "@/components/landing/landing-feature-catalog";
import type { LandingFeatureId } from "@/components/landing/landing-feature-catalog";
import { LandingMotionRoot, m, useReducedMotion } from "@/components/landing/landing-motion";
import { LandingSection } from "@/components/landing/landing-section";
import { Button } from "@/components/ui/button";

export function LandingFeatureCardGrid({ copy }: { copy: LandingCopy }) {
  const [openId, setOpenId] = useState<LandingFeatureId | null>(null);
  const reduce = useReducedMotion();
  const openFeature = openId ? copy.features[openId] : null;

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
        <LandingMotionRoot>
          <AnimatePresence initial={false}>
            {openFeature && openId ? (
              <m.div
                id={LANDING_FEATURE_DETAIL_ID}
                key={openId}
                className="norgoth-landing-card-detail"
                initial={reduce ? false : { height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={reduce ? { opacity: 1 } : { height: 0, opacity: 0 }}
                transition={{ duration: reduce ? 0 : 0.28 }}
                style={{ overflow: "hidden" }}
              >
                <div className="d-flex justify-content-between align-items-start gap-3">
                  <h3 className="h5 mb-2">{openFeature.title}</h3>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setOpenId(null)}
                  >
                    {copy.cardsDetailClose}
                  </Button>
                </div>
                <p className="small mb-3">{openFeature.body}</p>
                <ul className="mb-0 ps-3 small text-body-secondary">
                  <li>{openFeature.cap1}</li>
                  <li>{openFeature.cap2}</li>
                  <li>{openFeature.cap3}</li>
                </ul>
              </m.div>
            ) : null}
          </AnimatePresence>
        </LandingMotionRoot>
      </div>
    </LandingSection>
  );
}
