const DISCORD_CDN_BASE = "https://cdn.discordapp.com";

export function discordIconUrl(
  guildId: string,
  iconHash: string | null | undefined,
  size = 128,
): string | null {
  if (!guildId || !iconHash) return null;
  const ext = iconHash.startsWith("a_") ? "gif" : "png";
  return `${DISCORD_CDN_BASE}/icons/${guildId}/${iconHash}.${ext}?size=${size}`;
}
