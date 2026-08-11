"use client";

/**
 * Compatibility shim — re-exports guild store hook so existing imports keep working
 * while panels migrate to `@/stores/guild-store` directly.
 */
export {
  useFirstGuild,
  type GuildResources,
  type GuildRole,
  type GuildChannel,
  type GuildCategory,
} from "@/stores/guild-store";
