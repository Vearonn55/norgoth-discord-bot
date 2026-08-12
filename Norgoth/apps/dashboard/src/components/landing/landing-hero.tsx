"use client";

import { CContainer } from "@coreui/react";
import { Button } from "@/components/ui/button";
import type { LandingCopy } from "@/components/landing/landing-copy";

export function LandingHero({
  copy,
  loginHref,
}: {
  copy: LandingCopy;
  loginHref: string;
}) {
  return (
    <section className="norgoth-landing-hero py-5">
      <CContainer style={{ maxWidth: 1100 }}>
        <div className="row g-4 align-items-center">
          <div className="col-lg-7 norgoth-landing-hero-copy">
            <p
              className="mb-2 fw-bold text-uppercase"
              style={{ letterSpacing: "0.18em", color: "var(--cui-primary)" }}
            >
              {copy.heroEyebrow}
            </p>
            <h1
              className="display-5 fw-bold mb-3"
              style={{ lineHeight: 1.15, maxWidth: 640 }}
            >
              {copy.heroTitle1}
              <br />
              {copy.heroTitle2}
              <br />
              {copy.heroTitle3}
            </h1>
            <p
              className="lead text-body-secondary mb-4"
              style={{ maxWidth: 640 }}
            >
              {copy.heroLead}
            </p>
            <div className="d-flex flex-wrap gap-2">
              <Button asChild variant="primary" size="lg">
                <a href={loginHref}>{copy.login}</a>
              </Button>
            </div>
          </div>
          <div className="col-lg-5 d-none d-lg-block">
            <div className="norgoth-landing-silhouette" aria-hidden="true">
              <div className="norgoth-landing-silhouette-sidebar" />
              <div className="norgoth-landing-silhouette-main">
                <div className="norgoth-landing-silhouette-bar" />
                <div className="norgoth-landing-silhouette-grid">
                  <div />
                  <div />
                  <div />
                  <div />
                </div>
              </div>
            </div>
          </div>
        </div>
      </CContainer>
    </section>
  );
}
