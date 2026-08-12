"use client";

import Link from "next/link";
import { CContainer } from "@coreui/react";
import { Button } from "@/components/ui/button";
import type { LandingCopy } from "@/components/landing/landing-copy";

export function LandingNav({
  lang,
  copy,
  loginHref,
  addBotHref,
}: {
  lang: string;
  copy: LandingCopy;
  loginHref: string;
  addBotHref: string;
}) {
  const otherLang = lang === "tr" ? "en" : "tr";
  const otherLabel = lang === "tr" ? copy.langEn : copy.langTr;

  return (
    <header className="norgoth-landing-nav border-bottom border-secondary-subtle">
      <CContainer
        className="d-flex align-items-center justify-content-between py-3 gap-3"
        style={{ maxWidth: 1100 }}
      >
        <Link
          href={`/${lang}`}
          className="text-decoration-none fw-bold text-body"
          style={{ fontSize: "1.25rem", letterSpacing: "0.04em" }}
        >
          {copy.navBrand}
        </Link>
        <nav className="d-none d-md-flex align-items-center gap-3 small">
          <a href="#how-it-works" className="text-decoration-none text-body-secondary">
            {copy.navHow}
          </a>
          <a href="#features" className="text-decoration-none text-body-secondary">
            {copy.navFeatures}
          </a>
        </nav>
        <div className="d-flex align-items-center gap-2">
          <Link
            href={`/${otherLang}`}
            className="small text-decoration-none text-body-secondary me-1"
          >
            {otherLabel}
          </Link>
          <Button asChild variant="secondary">
            <a href={addBotHref}>{copy.addToDiscord}</a>
          </Button>
          <Button asChild variant="primary">
            <a href={loginHref}>{copy.login}</a>
          </Button>
        </div>
      </CContainer>
    </header>
  );
}
