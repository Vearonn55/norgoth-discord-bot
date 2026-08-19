import Link from "next/link";
import { LandingCtas } from "@/components/landing/landing-ctas";
import { LandingMobileNav } from "@/components/landing/landing-mobile-nav";
import type { LandingCopy } from "@/components/landing/landing-copy";

export function LandingNav({
  lang,
  copy,
  loginHref,
  inviteHref,
}: {
  lang: string;
  copy: LandingCopy;
  loginHref: string;
  inviteHref: string;
}) {
  const otherLang = lang === "tr" ? "en" : "tr";
  const otherLabel = lang === "tr" ? copy.langEn : copy.langTr;

  return (
    <header className="norgoth-landing-nav border-bottom border-secondary-subtle">
      <div
        className="container position-relative d-flex align-items-center justify-content-between py-3 gap-3"
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
          <a href="#features" className="text-decoration-none text-body-secondary">
            {copy.navFeatures}
          </a>
          <a href="#why" className="text-decoration-none text-body-secondary">
            {copy.navWhy}
          </a>
          <a href="#how-it-works" className="text-decoration-none text-body-secondary">
            {copy.navHow}
          </a>
          <a href="#trust" className="text-decoration-none text-body-secondary">
            {copy.navTrust}
          </a>
        </nav>
        <div className="d-none d-md-flex align-items-center gap-2">
          <Link
            href={`/${otherLang}`}
            className="small text-decoration-none text-body-secondary me-1"
          >
            {otherLabel}
          </Link>
          <LandingCtas
            copy={copy}
            loginHref={loginHref}
            inviteHref={inviteHref}
            size="md"
          />
        </div>
        <div className="d-flex d-md-none align-items-center gap-2">
          <Link
            href={`/${otherLang}`}
            className="small text-decoration-none text-body-secondary"
          >
            {otherLabel}
          </Link>
          <LandingMobileNav
            copy={copy}
            loginHref={loginHref}
            inviteHref={inviteHref}
          />
        </div>
      </div>
    </header>
  );
}
