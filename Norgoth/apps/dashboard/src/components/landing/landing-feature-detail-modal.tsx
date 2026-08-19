"use client";

import { useEffect, useRef } from "react";
import {
  CModal,
  CModalBody,
  CModalFooter,
  CModalHeader,
  CModalTitle,
} from "@coreui/react";
import { CIcon } from "@coreui/icons-react";
import type { LandingCopy } from "@/components/landing/landing-copy";
import type { LandingFeatureId } from "@/components/landing/landing-feature-catalog";
import {
  landingFeatureDef,
  landingNavGroupLabel,
} from "@/components/landing/landing-feature-catalog";
import { Button } from "@/components/ui/button";
import { shouldInvokeModalClose } from "@/lib/cn-url-state";
import { CATEGORY_TOKENS } from "@/lib/design/category";

export const LANDING_FEATURE_DETAIL_MODAL_ID = "landing-feature-detail-modal";

export function LandingFeatureDetailModal({
  openId,
  copy,
  sidebar,
  onClose,
}: {
  openId: LandingFeatureId | null;
  copy: LandingCopy;
  sidebar: Record<string, string>;
  onClose: () => void;
}) {
  const visible = openId !== null;
  const openerRef = useRef<HTMLElement | null>(null);
  const wasVisible = useRef(false);

  useEffect(() => {
    if (visible && !wasVisible.current) {
      openerRef.current =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
    }
    if (!visible && wasVisible.current) {
      const opener = openerRef.current;
      if (opener) queueMicrotask(() => opener.focus());
    }
    wasVisible.current = visible;
  }, [visible]);

  function handleClose() {
    if (!shouldInvokeModalClose(visible)) return;
    onClose();
  }

  const feature = openId ? copy.features[openId] : null;
  const def = openId ? landingFeatureDef(openId) : null;
  const groupLabel = openId ? landingNavGroupLabel(openId, sidebar) : "";
  const tokens = def ? CATEGORY_TOKENS[def.category] : null;

  return (
    <CModal
      id={LANDING_FEATURE_DETAIL_MODAL_ID}
      visible={visible}
      onClose={handleClose}
      size="lg"
      alignment="center"
      scrollable
      backdrop
      className="norgoth-landing-feature-modal"
    >
      {feature && def && tokens ? (
        <>
          <CModalHeader style={{ borderBottomColor: tokens.color }}>
            <CModalTitle>
              <span className="d-flex align-items-center gap-2">
                <CIcon
                  icon={def.icon}
                  height={20}
                  aria-hidden="true"
                  style={{ color: tokens.color }}
                />
                <span>{feature.title}</span>
              </span>
              <span
                className="d-block small fw-normal mt-1"
                style={{ letterSpacing: "0.06em", color: tokens.color }}
              >
                {groupLabel}
              </span>
            </CModalTitle>
          </CModalHeader>
          <CModalBody>
            <div key={openId}>
              <p className="mb-3">{feature.body}</p>
              <ul className="mb-0 ps-3 text-body-secondary">
                <li>{feature.cap1}</li>
                <li>{feature.cap2}</li>
                <li>{feature.cap3}</li>
              </ul>
            </div>
          </CModalBody>
          <CModalFooter>
            <Button variant="secondary" onClick={handleClose}>
              {copy.cardsDetailClose}
            </Button>
          </CModalFooter>
        </>
      ) : null}
    </CModal>
  );
}
