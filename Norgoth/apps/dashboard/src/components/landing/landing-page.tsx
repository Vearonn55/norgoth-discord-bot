"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { CAlert, CContainer } from "@coreui/react";
import { Button } from "@/components/ui/button";
import { browserApiUrl } from "@/lib/api";

const FEATURE_CATEGORIES = [
  {
    title: "Community",
    items: [
      "Member Verification",
      "Self-Assignable Roles",
      "Leveling",
      "Invite Tracking",
      "Welcome & Leave Messages",
    ],
  },
    {
        title: "Moderation & Security",
        items: [
          "Rule-Based Auto-Moderation",
          "Raid Protection",
          "Honeypot Trap Channels",
          "Audit & Moderation Logs",
          "Server Event Logging",
        ],
      },
  {
    title: "Communication",
    items: ["Campaigns", "Announcements", "Message Composer", "Delivery Analytics"],
  },
  {
    title: "Support",
    items: ["Tickets", "Support Teams", "Ticket Transcripts"],
  },
  {
    title: "Automation",
    items: ["Auto Responses", "Stream Notifications", "Role Menus"],
  },
  {
    title: "Operations",
    items: ["Queue Monitoring", "Worker Health", "Community Analytics"],
  },
] as const;

export function LandingPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const lang = String(params?.lang ?? "en");
  const oauthError = searchParams.get("oauth_error");

  // Dev bypass: when auth is not enforced, skip Discord OAuth and go straight
  // into the app. Re-enable login by setting NEXT_PUBLIC_AUTH_ENFORCED=true.
  const authBypassed = process.env.NEXT_PUBLIC_AUTH_ENFORCED === "false";
  const loginHref = authBypassed
    ? `/${lang}/servers`
    : browserApiUrl(
        `/api/v1/oauth/discord/dashboard/authorize?lang=${encodeURIComponent(lang)}`
      );

  const addBotHref = browserApiUrl(`/api/v1/oauth/discord/bot-invite`);

  return (
    <>
      <header className="norgoth-landing-nav border-bottom border-secondary-subtle">
        <CContainer
          className="d-flex align-items-center justify-content-between py-3"
          style={{ maxWidth: 1100 }}
        >
          <Link
            href={`/${lang}`}
            className="text-decoration-none fw-bold text-body"
            style={{ fontSize: "1.25rem", letterSpacing: "0.04em" }}
          >
            NORGOTH
          </Link>
          <div className="d-flex align-items-center gap-2">
            <Button asChild variant="secondary">
              <a href={addBotHref}>Add to Discord</a>
            </Button>
            <Button asChild variant="primary">
              <a href={loginHref}>Login with Discord</a>
            </Button>
          </div>
        </CContainer>
      </header>

      {oauthError === "not_configured" ? (
        <CContainer style={{ maxWidth: 1100 }} className="pt-4">
          <CAlert color="warning" className="mb-0">
            <strong>Discord OAuth is not configured.</strong> Set{" "}
            <code>NORGOTH_DISCORD_CLIENT_ID</code>,{" "}
            <code>NORGOTH_DISCORD_CLIENT_SECRET</code>, and{" "}
            <code>NORGOTH_DISCORD_REDIRECT_URI</code> in{" "}
            <code>Norgoth/.env</code>, then restart the API. The Client Secret
            comes from the Discord Developer Portal → OAuth2.
          </CAlert>
        </CContainer>
      ) : null}

      {oauthError && oauthError !== "not_configured" ? (
        <CContainer style={{ maxWidth: 1100 }} className="pt-4">
          <CAlert color="danger" className="mb-0">
            Discord login failed. Please try again.
          </CAlert>
        </CContainer>
      ) : null}

      <main className="flex-grow-1">
        <section className="norgoth-landing-hero py-5">
          <CContainer style={{ maxWidth: 1100 }}>
            <p
              className="mb-2 fw-bold text-uppercase"
              style={{ letterSpacing: "0.18em", color: "var(--cui-primary)" }}
            >
              NORGOTH
            </p>
            <h1
              className="display-5 fw-bold mb-3"
              style={{ lineHeight: 1.15, maxWidth: 640 }}
            >
              One bot.
              <br />
              One dashboard.
              <br />
              Your whole Discord community.
            </h1>
            <p
              className="lead text-body-secondary mb-4"
              style={{ maxWidth: 640 }}
            >
              Norgoth combines community management, moderation, security,
              messaging, automation, and support into a single Discord bot and
              one Community Command Center — so you are not juggling three or
              four specialized bots and dashboards.
            </p>
            <div className="d-flex flex-wrap gap-2">
              <Button asChild variant="primary" size="lg">
                <a href={loginHref}>Login with Discord</a>
              </Button>
              <Button asChild variant="secondary" size="lg">
                <a href={addBotHref}>Add Norgoth to Discord</a>
              </Button>
            </div>
          </CContainer>
        </section>

        <section className="py-5 border-top border-secondary-subtle">
          <CContainer style={{ maxWidth: 1100 }}>
            <h2 className="h3 mb-2">Why Norgoth exists</h2>
            <p className="text-body-secondary mb-4" style={{ maxWidth: 720 }}>
              Server administrators often install many independent bots for
              moderation, security, leveling, roles, logging, tickets, and
              announcements. That creates configuration fragmentation and
              inconsistent admin experiences. Norgoth consolidates those
              workflows.
            </p>
            <div className="row g-3">
              {[
                {
                  title: "Fewer bots",
                  body: "Run one unified bot instead of a stack of single-purpose tools.",
                },
                {
                  title: "Fewer dashboards",
                  body: "Operate verification, campaigns, tickets, and security from one Command Center.",
                },
                {
                  title: "Less fragmentation",
                  body: "Shared guild context, logging, and permissions across every module.",
                },
              ].map((item) => (
                <div key={item.title} className="col-md-4">
                  <div className="norgoth-section-card norgoth-section-card-primary h-100 p-3">
                    <h3 className="h5">{item.title}</h3>
                    <p className="mb-0 small text-body-secondary">{item.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </CContainer>
        </section>

        <section className="py-5 border-top border-secondary-subtle">
          <CContainer style={{ maxWidth: 1100 }}>
            <h2 className="h3 mb-2">What you can run today</h2>
            <p className="text-body-secondary mb-4">
              Feature list reflects capabilities shipped in the Norgoth
              repository — not marketing placeholders.
            </p>
            <div className="row g-3">
              {FEATURE_CATEGORIES.map((cat) => (
                <div key={cat.title} className="col-md-6 col-lg-4">
                  <div className="norgoth-section-card norgoth-section-card-secondary h-100 p-3">
                    <h3 className="h6 text-uppercase mb-3" style={{ letterSpacing: "0.06em" }}>
                      {cat.title}
                    </h3>
                    <ul className="mb-0 ps-3 small">
                      {cat.items.map((item) => (
                        <li key={item} className="mb-1">
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ))}
            </div>
          </CContainer>
        </section>

        <section className="py-5 border-top border-secondary-subtle">
          <CContainer style={{ maxWidth: 1100 }} className="text-center">
            <h2 className="h3 mb-3">Ready to manage your community</h2>
            <p className="text-body-secondary mb-4 mx-auto" style={{ maxWidth: 520 }}>
              Sign in with Discord, pick a server you manage, and open the
              Command Center for that guild only.
            </p>
            <Button asChild variant="primary" size="lg">
              <a href={loginHref}>Login with Discord</a>
            </Button>
          </CContainer>
        </section>
      </main>

      <footer className="border-top border-secondary-subtle py-4 mt-auto">
        <CContainer
          className="d-flex flex-wrap justify-content-between gap-2 small text-body-secondary"
          style={{ maxWidth: 1100 }}
        >
          <span>Norgoth Community Command Center</span>
          <span>One bot. One dashboard. Your whole Discord community.</span>
        </CContainer>
      </footer>
    </>
  );
}
