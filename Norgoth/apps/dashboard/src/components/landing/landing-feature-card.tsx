"use client";

import { CIcon } from "@coreui/icons-react";
import type { LandingCopy } from "@/components/landing/landing-copy";
import type { LandingFeatureId } from "@/components/landing/landing-feature-catalog";
import { landingFeatureDef } from "@/components/landing/landing-feature-catalog";
import { LANDING_FEATURE_DETAIL_MODAL_ID } from "@/components/landing/landing-feature-detail-modal";
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
  const def = landingFeatureDef(id);
  const feature = copy.features[id];
  const tokens = CATEGORY_TOKENS[def.category];

  return (
    <button
      type="button"
      className="norgoth-landing-card norgoth-mini-card w-100 p-3"
      style={{
        minHeight: 40,
        borderLeft: `3px solid ${tokens.color}`,
      }}
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-controls={LANDING_FEATURE_DETAIL_MODAL_ID}
      onClick={() => onToggle(id)}
    >
      <span className="norgoth-landing-card-icon" aria-hidden="true">
        <CIcon icon={def.icon} />
      </span>
      <span className="norgoth-landing-card-title">{feature.title}</span>
      <span className="norgoth-landing-card-summary small text-body-secondary">
        {feature.summary}
      </span>
      <span className="visually-hidden">
        {open ? copy.cardsCollapse : copy.cardsExpand}
      </span>
    </button>
  );
}
