import Link from "next/link";
import type { VerificationVisualState } from "../_lib/verification-public";
import { GuildIcon } from "@/components/ui/guild-icon";

type ShellCopy = {
  brand: string;
  trustTitle: string;
  trustBody: string;
  footer: string;
  stepConnect: string;
  stepSecurity: string;
  stepRole: string;
  retry: string;
  returnDiscord: string;
  reference: string;
  discordAccountHint?: string;
  discordAccountSettingsLabel?: string;
};

type Action = {
  label: string;
  href: string;
};

const STATE_ACCENT_CLASS: Record<VerificationVisualState, string> = {
  ready: "norgoth-verify-accent-primary",
  processing: "norgoth-verify-accent-info",
  success: "norgoth-verify-accent-success",
  manual_review: "norgoth-verify-accent-warning",
  denied: "norgoth-verify-accent-danger",
  error: "norgoth-verify-accent-danger",
  unavailable: "norgoth-verify-accent-warning",
};

export function VerificationPublicShell({
  copy,
  state,
  title,
  description,
  guildName,
  guildIconUrl,
  primaryAction,
  secondaryAction,
  referenceId,
  progressStep = 0,
  liveMessage,
  showDiscordAccountHint = false,
}: {
  copy: ShellCopy;
  state: VerificationVisualState;
  title: string;
  description: string;
  guildName?: string;
  guildIconUrl?: string | null;
  primaryAction?: Action;
  secondaryAction?: Action;
  referenceId?: string;
  progressStep?: 0 | 1 | 2;
  liveMessage?: string;
  showDiscordAccountHint?: boolean;
}) {
  return (
    <main className="norgoth-verify-wrap container py-4 py-md-5">
      <div className="norgoth-verify-center mx-auto">
        <section className={`norgoth-verify-card ${STATE_ACCENT_CLASS[state]}`}>
          <header className="d-flex align-items-center gap-3 mb-3">
            {guildName ? (
              <GuildIcon url={guildIconUrl ?? null} name={guildName} size={44} />
            ) : (
              <span className="norgoth-verify-brand-dot" aria-hidden="true">
                N
              </span>
            )}
            <div className="min-w-0">
              <p className="mb-0 text-body-tertiary small">{copy.brand}</p>
              {guildName ? (
                <p className="mb-0 text-body-secondary fw-semibold text-break">
                  {guildName}
                </p>
              ) : null}
            </div>
          </header>

          <ol className="norgoth-verify-steps mb-3" aria-label={copy.stepConnect}>
            <li className={progressStep >= 0 ? "is-active" : ""}>{copy.stepConnect}</li>
            <li className={progressStep >= 1 ? "is-active" : ""}>{copy.stepSecurity}</li>
            <li className={progressStep >= 2 ? "is-active" : ""}>{copy.stepRole}</li>
          </ol>

          <h1 className="h3 mb-2">{title}</h1>
          <p className="text-body-secondary mb-0">{description}</p>
          {showDiscordAccountHint && copy.discordAccountHint ? (
            <div className="mt-3">
              <p className="text-body-secondary small mb-2">{copy.discordAccountHint}</p>
              {copy.discordAccountSettingsLabel ? (
                <a
                  href="https://discord.com/settings/account"
                  className="small"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {copy.discordAccountSettingsLabel}
                </a>
              ) : null}
            </div>
          ) : null}
          {liveMessage ? (
            <p className="visually-hidden" aria-live="polite">
              {liveMessage}
            </p>
          ) : null}

          <div className="d-flex flex-column flex-sm-row gap-2 mt-4">
            {primaryAction ? (
              <Link href={primaryAction.href} className="btn btn-primary">
                {primaryAction.label}
              </Link>
            ) : null}
            {secondaryAction ? (
              <Link href={secondaryAction.href} className="btn btn-secondary">
                {secondaryAction.label}
              </Link>
            ) : null}
          </div>

          {referenceId ? (
            <p className="small text-body-tertiary mt-3 mb-0 text-break">
              {copy.reference.replace("{cid}", referenceId)}
            </p>
          ) : null}
        </section>

        <section className="norgoth-verify-trust mt-3" aria-label={copy.trustTitle}>
          <h2 className="h6 mb-1">{copy.trustTitle}</h2>
          <p className="small text-body-secondary mb-0">{copy.trustBody}</p>
        </section>

        <footer className="norgoth-verify-footer small text-body-tertiary mt-3">
          {copy.footer}
        </footer>
      </div>
    </main>
  );
}
