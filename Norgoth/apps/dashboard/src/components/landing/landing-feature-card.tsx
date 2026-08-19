"use client";

import { AnimatePresence } from "motion/react";
import { CIcon } from "@coreui/icons-react";
import type { LandingCopy } from "@/components/landing/landing-copy";
import type { LandingFeatureId } from "@/components/landing/landing-feature-catalog";
import { landingFeatureDef } from "@/components/landing/landing-feature-catalog";
import { m, useReducedMotion } from "@/components/landing/landing-motion";
import { CATEGORY_TOKENS } from "@/lib/design/category";

export function LandingFeatureCard({
  id,
  copy,
  open,
  onToggle,
}: {
  id: LandingFeatureId;
  copy: LandingCopy;
  open: boolean;
  onToggle: (id: LandingFeatureId) => void;
}) {
  const reduce = useReducedMotion();
  const def = landingFeatureDef(id);
  const feature = copy.features[id];
  const detailId = `landing-card-detail-${id}`;
  const tokens = CATEGORY_TOKENS[def.category];

  return (
    <div>
      <button
        type="button"
        className="norgoth-landing-card norgoth-mini-card w-100 p-3"
        style={{
          minHeight: 40,
          borderLeft: `3px solid ${tokens.color}`,
        }}
        aria-expanded={open}
        aria-controls={detailId}
        onClick={() => onToggle(id)}
        onKeyDown={(event) => {
          if (event.key === "Escape" && open) {
            event.preventDefault();
            onToggle(id);
          }
        }}
      >
        <span className="d-flex align-items-start gap-2">
          <CIcon icon={def.icon} className="mt-1 flex-shrink-0" />
          <span>
            <span className="d-block fw-semibold">{feature.title}</span>
            <span className="d-block small text-body-secondary">{feature.summary}</span>
            <span className="visually-hidden">
              {open ? copy.cardsCollapse : copy.cardsExpand}
            </span>
          </span>
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open ? (
          <m.div
            id={detailId}
            key={detailId}
            initial={reduce ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduce ? { opacity: 1 } : { height: 0, opacity: 0 }}
            transition={{ duration: reduce ? 0 : 0.28 }}
            style={{ overflow: "hidden" }}
          >
            <p className="small text-body-secondary mb-0 pt-2 px-1">{feature.body}</p>
          </m.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
