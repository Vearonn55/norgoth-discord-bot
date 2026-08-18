import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasLocale } from "../../../dictionaries";
import { getDictionary } from "../../../dictionaries";
import type { Locale } from "@/i18n/config";
import { browserApiUrl } from "@/lib/api";
import { VerificationPublicShell } from "../_components/verification-public-shell";
import {
  mapOutcomeToVisualState,
  resolveDisplayContext,
} from "../_lib/verification-public";

const OUTCOME_TITLES: Record<string, "titleGranted" | "titlePending" | "titleDenied" | "titleError"> =
  {
    granted: "titleGranted",
    pending: "titlePending",
    denied: "titleDenied",
    error: "titleError",
  };

export async function generateMetadata(): Promise<Metadata> {
  return {
    robots: { index: false, follow: false },
  };
}

export default async function VerifyResultPage({
  params,
  searchParams,
}: {
  params: Promise<{ lang: string }>;
  searchParams: Promise<{
    outcome?: string;
    reason?: string;
    cid?: string;
    ctx?: string;
  }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const query = await searchParams;
  const dict = await getDictionary(lang as Locale);
  const copy = dict.verifyResultPage;
  const shellCopy = dict.verifyPublicPage;
  const outcome = (query.outcome || "error").toLowerCase();
  const reason = (query.reason || "").toLowerCase();
  const titleKey = OUTCOME_TITLES[outcome] ?? "titleError";
  const context = await resolveDisplayContext(query.ctx);
  const visualState = mapOutcomeToVisualState(outcome);
  const reasonCopy =
    (copy as Record<string, string>)[reason] ||
    (outcome === "granted"
      ? copy.granted
      : outcome === "pending"
        ? copy.pending
        : outcome === "denied"
          ? copy.denied
          : copy.internal_error);

  const retryableReasons = new Set([
    "oauth_invalid",
    "oauth_expired",
    "discord_rate_limited",
    "discord_unavailable",
    "client_ip_unavailable",
    "verification_processing_failed",
  ]);
  const retryAction =
    context && (outcome === "error" || retryableReasons.has(reason))
      ? {
          label: shellCopy.retry,
          href: browserApiUrl(
            `/api/v1/oauth/discord/authorize/${context.guild_id}?lang=${encodeURIComponent(lang)}&start=1`,
          ),
        }
      : undefined;

  const returnAction =
    outcome === "granted" || outcome === "pending"
      ? {
          label: shellCopy.returnDiscord,
          href: "https://discord.com/app",
        }
      : undefined;

  return (
    <VerificationPublicShell
      copy={shellCopy}
      state={visualState}
      title={copy[titleKey]}
      description={reasonCopy}
      guildName={context?.guild_name}
      guildIconUrl={context?.guild_icon_url}
      primaryAction={returnAction}
      secondaryAction={retryAction}
      referenceId={query.cid}
      progressStep={outcome === "granted" ? 2 : outcome === "pending" ? 1 : 1}
      liveMessage={copy[titleKey]}
    />
  );
}
