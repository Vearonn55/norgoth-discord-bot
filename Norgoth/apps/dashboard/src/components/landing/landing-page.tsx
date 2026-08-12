"use client";

import { useSearchParams } from "next/navigation";
import { CAlert, CContainer } from "@coreui/react";
import { browserApiUrl } from "@/lib/api";
import { botInviteHref } from "@/lib/bot-invite";
import type { LandingCopy } from "@/components/landing/landing-copy";
import { LandingNav } from "@/components/landing/landing-nav";
import { LandingHero } from "@/components/landing/landing-hero";
import { LandingValue } from "@/components/landing/landing-value";
import { LandingFeatures } from "@/components/landing/landing-features";
import { LandingHowItWorks } from "@/components/landing/landing-how-it-works";
import { LandingTrust } from "@/components/landing/landing-trust";
import { LandingCta } from "@/components/landing/landing-cta";
import { LandingFooter } from "@/components/landing/landing-footer";

export function LandingPage({
  copy,
  lang,
}: {
  copy: LandingCopy;
  lang: string;
}) {
  const searchParams = useSearchParams();
  const oauthError = searchParams.get("oauth_error");

  const authBypassed = process.env.NEXT_PUBLIC_AUTH_ENFORCED === "false";
  const loginHref = authBypassed
    ? `/${lang}/servers`
    : browserApiUrl(
        `/api/v1/oauth/discord/dashboard/authorize?lang=${encodeURIComponent(lang)}`,
      );

  const addBotHref = botInviteHref();

  return (
    <>
      <LandingNav
        lang={lang}
        copy={copy}
        loginHref={loginHref}
        addBotHref={addBotHref}
      />

      {oauthError === "not_configured" ? (
        <CContainer style={{ maxWidth: 1100 }} className="pt-4">
          <CAlert color="warning" className="mb-0">
            <strong>{copy.oauthNotConfiguredTitle}</strong>{" "}
            {copy.oauthNotConfiguredBody}
          </CAlert>
        </CContainer>
      ) : null}

      {oauthError && oauthError !== "not_configured" ? (
        <CContainer style={{ maxWidth: 1100 }} className="pt-4">
          <CAlert color="danger" className="mb-0">
            {copy.oauthFailed}
          </CAlert>
        </CContainer>
      ) : null}

      <main className="flex-grow-1">
        <LandingHero
          copy={copy}
          loginHref={loginHref}
          addBotHref={addBotHref}
        />
        <LandingValue copy={copy} />
        <LandingFeatures copy={copy} />
        <LandingHowItWorks copy={copy} />
        <LandingTrust copy={copy} />
        <LandingCta copy={copy} loginHref={loginHref} />
      </main>

      <LandingFooter lang={lang} copy={copy} />
    </>
  );
}
