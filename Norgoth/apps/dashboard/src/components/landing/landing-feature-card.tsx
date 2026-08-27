"use client";

import { useRef } from "react";
import { CIcon } from "@coreui/icons-react";
import type { LandingCopy } from "@/components/landing/landing-copy";
import type { LandingFeatureId } from "@/components/landing/landing-feature-catalog";
import {
  landingFeatureDef,
  landingNavGroupLabel,
} from "@/components/landing/landing-feature-catalog";
import { CATEGORY_TOKENS } from "@/lib/design/category";

export function landingFeatureOverlayId(id: LandingFeatureId): string {
  return `landing-feature-overlay-${id}`;
}

export function LandingFeatureCard({
  id,
  copy,
  sidebar,
  open,
  onOpen,
  onClose,
  onToggle,
}: {
  id: LandingFeatureId;
  copy: LandingCopy;
  sidebar: Record<string, string>;
  open: boolean;
  onOpen: (id: LandingFeatureId) => void;
  onClose: (id: LandingFeatureId) => void;
  onToggle: (id: LandingFeatureId) => void;
}) {
  const shellRef = useRef<HTMLDivElement | null>(null);
  const def = landingFeatureDef(id);
  const feature = copy.features[id];
  const tokens = CATEGORY_TOKENS[def.category];
  const overlayId = landingFeatureOverlayId(id);
  const titleId = `landing-feature-title-${id}`;
  const groupLabel = landingNavGroupLabel(id, sidebar);

  return (
    <div
      ref={shellRef}
      className="norgoth-landing-card norgoth-mini-card"
      data-feature-id={id}
      data-open={open ? "true" : undefined}
      style={{ borderLeft: `3px solid ${tokens.color}` }}
      onPointerEnter={(event) => {
        if (event.pointerType === "touch") return;
        onOpen(id);
      }}
      onPointerLeave={() => {
        if (
          shellRef.current &&
          document.activeElement instanceof Node &&
          shellRef.current.contains(document.activeElement)
        ) {
          return;
        }
        onClose(id);
      }}
      onFocusCapture={() => {
        onOpen(id);
      }}
      onBlurCapture={(event) => {
        const next = event.relatedTarget;
        if (next instanceof Node && shellRef.current?.contains(next)) {
          return;
        }
        onClose(id);
      }}
    >
      <button
        type="button"
        className="norgoth-landing-card-face w-100 p-3 border-0 bg-transparent text-start"
        aria-expanded={open}
        aria-controls={overlayId}
        onClick={() => onToggle(id)}
      >
        <span className="norgoth-landing-card-icon" aria-hidden="true">
          <CIcon icon={def.icon} />
        </span>
        <span className="norgoth-landing-card-title" id={titleId}>
          {feature.title}
        </span>
        <span className="norgoth-landing-card-summary small text-body-secondary">
          {feature.summary}
        </span>
        <span className="visually-hidden">
          {open ? copy.cardsCollapse : copy.cardsExpand}
        </span>
      </button>

      <div
        id={overlayId}
        className="norgoth-landing-card-overlay"
        role="region"
        aria-labelledby={titleId}
        hidden={!open}
        inert={!open}
      >
        <div className="norgoth-landing-card-overlay-inner">
          <div className="norgoth-landing-card-overlay-header">
            <span
              className="norgoth-landing-card-icon"
              aria-hidden="true"
              style={{ color: tokens.color }}
            >
              <CIcon icon={def.icon} />
            </span>
            <span className="min-w-0">
              <span className="d-block fw-semibold text-truncate">
                {feature.title}
              </span>
              <span
                className="d-block small"
                style={{ letterSpacing: "0.06em", color: tokens.color }}
              >
                {groupLabel}
              </span>
            </span>
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary norgoth-landing-card-overlay-close ms-auto flex-shrink-0"
              onClick={(event) => {
                event.stopPropagation();
                onClose(id);
              }}
            >
              {copy.cardsDetailClose}
            </button>
          </div>
          <div className="norgoth-landing-card-overlay-body norgoth-scrollbar">
            <p className="mb-2 small">{feature.body}</p>
            <ul className="mb-0 ps-3 small text-body-secondary">
              <li>{feature.cap1}</li>
              <li>{feature.cap2}</li>
              <li>{feature.cap3}</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
