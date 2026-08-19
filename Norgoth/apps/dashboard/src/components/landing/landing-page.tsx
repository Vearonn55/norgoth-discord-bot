import { Suspense } from "react";
import type { LandingCopy } from "@/components/landing/landing-copy";
import { LandingBackground } from "@/components/landing/landing-background";
import { LandingCta } from "@/components/landing/landing-cta";
import { LandingFeatureCardGrid } from "@/components/landing/landing-feature-card-grid";
import { LandingFeatureShowcase } from "@/components/landing/landing-features";
import { LandingFooter } from "@/components/landing/landing-footer";
import { LandingHero } from "@/components/landing/landing-hero";
import { LandingHowItWorks } from "@/components/landing/landing-how-it-works";
import { LandingNav } from "@/components/landing/landing-nav";
import { LandingOauthAlerts } from "@/components/landing/landing-oauth-alerts";
import { LandingTrust } from "@/components/landing/landing-trust";
import { LandingValue } from "@/components/landing/landing-value";
import { LandingWhy } from "@/components/landing/landing-why";
import { botInviteHref } from "@/lib/bot-invite";
import { dashboardLoginHref } from "@/lib/dashboard-login";

export function LandingPage({
  copy,
  sidebar,
  lang,
}: {
  copy: LandingCopy;
  sidebar: Record<string, string>;
  lang: string;
}) {
  const loginHref = dashboardLoginHref(lang);
  const inviteHref = botInviteHref();

  return (
    <div className="norgoth-landing-shell d-flex flex-column flex-grow-1">
      <LandingBackground />
      <a className="norgoth-skip-link" href="#main">
        {copy.skipToContent}
      </a>
      <LandingNav
        lang={lang}
        copy={copy}
        loginHref={loginHref}
        inviteHref={inviteHref}
      />
      <Suspense fallback={null}>
        <LandingOauthAlerts copy={copy} />
      </Suspense>
      <main id="main" className="flex-grow-1">
        <LandingHero
          copy={copy}
          loginHref={loginHref}
          inviteHref={inviteHref}
        />
        <LandingValue copy={copy} />
        <LandingFeatureShowcase copy={copy} sidebar={sidebar} />
        <LandingFeatureCardGrid copy={copy} />
        <LandingWhy copy={copy} />
        <LandingHowItWorks copy={copy} inviteHref={inviteHref} />
        <LandingTrust copy={copy} />
        <LandingCta
          copy={copy}
          loginHref={loginHref}
          inviteHref={inviteHref}
        />
      </main>
      <LandingFooter lang={lang} copy={copy} />
    </div>
  );
}
