import { browserApiUrl } from "@/lib/api";

/** Guild Install link. Omit guildId for the generic landing CTA. */
export function botInviteHref(guildId?: string): string {
  const path = guildId
    ? `/api/v1/oauth/discord/bot-invite?guild_id=${encodeURIComponent(guildId)}`
    : "/api/v1/oauth/discord/bot-invite";
  return browserApiUrl(path);
}
