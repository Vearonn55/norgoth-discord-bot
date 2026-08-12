"use client";

import { CContainer } from "@coreui/react";
import { Button } from "@/components/ui/button";
import { LandingSection } from "@/components/landing/landing-section";
import type { LandingCopy } from "@/components/landing/landing-copy";

export function LandingCta({
  copy,
  loginHref,
}: {
  copy: LandingCopy;
  loginHref: string;
}) {
  return (
    <LandingSection className="border-top border-secondary-subtle">
      <CContainer style={{ maxWidth: 1100 }} className="text-center">
        <h2 className="h3 mb-3">{copy.ctaTitle}</h2>
        <p
          className="text-body-secondary mb-4 mx-auto"
          style={{ maxWidth: 520 }}
        >
          {copy.ctaLead}
        </p>
        <Button asChild variant="primary" size="lg">
          <a href={loginHref}>{copy.login}</a>
        </Button>
      </CContainer>
    </LandingSection>
  );
}
