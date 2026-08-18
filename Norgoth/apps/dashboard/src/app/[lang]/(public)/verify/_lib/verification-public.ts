import { apiUrl, browserApiUrl } from "@/lib/api";

export type VerificationVisualState =
  | "ready"
  | "processing"
  | "success"
  | "manual_review"
  | "denied"
  | "error"
  | "unavailable";

export type VerificationDisplayContext = {
  guild_id: string;
  guild_name: string;
  guild_icon_url: string | null;
  lang: string;
};

export async function resolveDisplayContext(
  ctxToken?: string,
): Promise<VerificationDisplayContext | null> {
  if (!ctxToken) return null;
  try {
    const response = await fetch(
      apiUrl(`/api/v1/oauth/discord/display-context?ctx=${encodeURIComponent(ctxToken)}`),
      { cache: "no-store" },
    );
    if (!response.ok) return null;
    const data = (await response.json()) as VerificationDisplayContext;
    return data;
  } catch {
    return null;
  }
}

export function startVerificationHref(guildId: string, lang: string): string {
  return browserApiUrl(
    `/api/v1/oauth/discord/authorize/${guildId}?lang=${encodeURIComponent(lang)}&start=1`,
  );
}

export function mapOutcomeToVisualState(outcome: string): VerificationVisualState {
  if (outcome === "granted") return "success";
  if (outcome === "pending") return "manual_review";
  if (outcome === "denied") return "denied";
  return "error";
}

export function mapAuthorizeStateToVisualState(state: string): VerificationVisualState {
  if (state === "ready") return "ready";
  if (state === "degraded" || state === "error") return "unavailable";
  if (
    state === "not_configured" ||
    state === "incomplete" ||
    state === "disabled" ||
    state === "guild_not_found"
  ) {
    return "unavailable";
  }
  return "unavailable";
}
