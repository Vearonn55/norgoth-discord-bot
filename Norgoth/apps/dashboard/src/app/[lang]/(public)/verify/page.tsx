import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { Locale } from "@/i18n/config";
import { getDictionary, hasLocale } from "../../dictionaries";
import { VerificationPublicShell } from "./_components/verification-public-shell";
import {
  mapAuthorizeStateToVisualState,
  resolveDisplayContext,
  startVerificationHref,
} from "./_lib/verification-public";

export async function generateMetadata(): Promise<Metadata> {
  return {
    robots: { index: false, follow: false },
  };
}

export default async function VerifyStartPage({
  params,
  searchParams,
}: {
  params: Promise<{ lang: string }>;
  searchParams: Promise<{ state?: string; ctx?: string; retry?: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const query = await searchParams;
  const dict = await getDictionary(lang as Locale);
  const copy = dict.verifyPublicPage;
  const state = (query.state ?? "unavailable").toLowerCase();
  const visualState = mapAuthorizeStateToVisualState(state);
  const context = await resolveDisplayContext(query.ctx);

  const title =
    state === "ready"
      ? copy.readyTitle
      : (copy.stateMessages as Record<string, string>)[state] ?? copy.genericUnavailable;

  const description =
    state === "ready"
      ? copy.readyDescription
      : (copy.stateDetails as Record<string, string>)[state] ?? copy.contactAdmin;

  const primaryAction =
    state === "ready" && context
      ? {
          label: copy.connectDiscord,
          href: startVerificationHref(context.guild_id, lang),
        }
      : undefined;

  const secondaryAction =
    query.retry === "1" && context
      ? {
          label: copy.retry,
          href: startVerificationHref(context.guild_id, lang),
        }
      : undefined;

  return (
    <VerificationPublicShell
      copy={copy}
      state={visualState}
      title={title}
      description={description}
      guildName={context?.guild_name}
      guildIconUrl={context?.guild_icon_url}
      primaryAction={primaryAction}
      secondaryAction={secondaryAction}
      progressStep={state === "ready" ? 0 : 1}
    />
  );
}
