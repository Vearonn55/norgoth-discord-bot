"use client";

import { CAlert, CContainer } from "@coreui/react";
import { useSearchParams } from "next/navigation";
import type { LandingCopy } from "@/components/landing/landing-copy";

export function LandingOauthAlerts({ copy }: { copy: LandingCopy }) {
  const searchParams = useSearchParams();
  const oauthError = searchParams.get("oauth_error");

  if (!oauthError) {
    return null;
  }

  if (oauthError === "not_configured") {
    return (
      <CContainer style={{ maxWidth: 1100 }} className="pt-4">
        <CAlert color="warning" className="mb-0">
          <strong>{copy.oauthNotConfiguredTitle}</strong>{" "}
          {copy.oauthNotConfiguredBody}
        </CAlert>
      </CContainer>
    );
  }

  return (
    <CContainer style={{ maxWidth: 1100 }} className="pt-4">
      <CAlert color="danger" className="mb-0">
        {copy.oauthFailed}
      </CAlert>
    </CContainer>
  );
}
