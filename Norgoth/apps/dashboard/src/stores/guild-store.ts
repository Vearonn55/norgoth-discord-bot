"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";
import { readApiError } from "@/lib/api-error";
import { discordIconUrl } from "@/lib/discord-icon-url";

export type GuildChannel = {
  id: string;
  name: string;
  category?: string | null;
};

export type GuildRole = {
  id: string;
  name: string;
  managed: boolean;
  color?: string;
  position?: number;
};

export type GuildCategory = {
  id: string;
  name: string;
};

export type GuildEmoji = {
  id: string;
  name: string;
  animated?: boolean;
};

export type GuildResources = {
  guild_id: string;
  guild_name: string;
  member_count?: number;
  channels: GuildChannel[];
  categories?: GuildCategory[];
  roles: GuildRole[];
  emojis?: GuildEmoji[];
};

export type SelectedGuild = {
  id: string;
  name: string;
  icon?: string | null;
  icon_url?: string | null;
  bot_installed: boolean;
};

const SELECTED_GUILD_KEY = "norgoth:selected-guild:v1";
const RESOURCE_TIMEOUT_MS = 20_000;

type GuildState = {
  guildId: string | null;
  selectedGuild: SelectedGuild | null;
  resources: GuildResources | null;
  loading: boolean;
  error: string | null;
  selectGuild: (guild: SelectedGuild) => Promise<void>;
  clearGuild: () => void;
  reload: () => Promise<void>;
};

type ResourceLoadFailure = {
  message: string;
  code: string;
};

function mapResourceErrorCode(code: string): string {
  switch (code) {
    case "bot_not_installed":
      return "NorBot is not installed in this server yet.";
    case "guild_resources_unavailable":
      return "Guild resources are not available yet. Make sure the bot is online and invited.";
    case "missing_bot_permissions":
      return "NorBot is missing permissions to read channels or roles in this server.";
    case "discord_rate_limited":
      return "Discord is rate-limiting guild resources. Please retry shortly.";
    case "discord_temporarily_unavailable":
      return "Discord is temporarily unavailable. Please retry shortly.";
    case "guild_access_denied":
      return "You do not have access to this server in NorBot.";
    case "authentication_required":
      return "Your session has expired. Sign in again to continue.";
    default:
      return "Could not load guild resources.";
  }
}

function resolvedGuildIcon(guild: {
  id: string;
  icon?: string | null;
  icon_url?: string | null;
}): string | null {
  return guild.icon_url ?? discordIconUrl(guild.id, guild.icon ?? null) ?? null;
}

async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    window.clearTimeout(timeout);
  }
}

async function loadResources(guildId: string): Promise<GuildResources> {
  let resourcesResponse: Response;
  try {
    resourcesResponse = await fetchWithTimeout(
      apiUrl(`/guilds/${guildId}/discord-resources`),
      { cache: "no-store", credentials: "include" },
      RESOURCE_TIMEOUT_MS,
    );
  } catch {
    throw {
      code: "resource_fetch_timeout",
      message:
        "Guild resource request timed out. Please retry while NorBot reconnects to Discord.",
    } satisfies ResourceLoadFailure;
  }

  if (!resourcesResponse.ok) {
    const apiError = await readApiError(resourcesResponse);
    const code =
      apiError.code !== "http_error"
        ? apiError.code
        : resourcesResponse.status === 401
          ? "authentication_required"
          : resourcesResponse.status === 403
            ? "guild_access_denied"
            : "guild_resources_unavailable";
    const mapped = mapResourceErrorCode(code);
    const message =
      apiError.code !== "http_error" && apiError.message
        ? apiError.message
        : mapped;
    throw { code, message } satisfies ResourceLoadFailure;
  }

  return (await resourcesResponse.json()) as GuildResources;
}

export const useGuildStore = create<GuildState>((set, get) => ({
  guildId: null,
  selectedGuild: null,
  resources: null,
  loading: true,
  error: null,

  clearGuild: () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(SELECTED_GUILD_KEY);
    }
    set({
      guildId: null,
      selectedGuild: null,
      resources: null,
      error: null,
      loading: false,
    });
  },

  selectGuild: async (guild) => {
    const normalizedGuild: SelectedGuild = {
      ...guild,
      icon_url: resolvedGuildIcon({
        id: guild.id,
        icon: guild.icon,
        icon_url: guild.icon_url,
      }),
    };

    set({
      loading: true,
      error: null,
      guildId: normalizedGuild.id,
      selectedGuild: normalizedGuild,
      resources: null,
    });

    if (typeof window !== "undefined") {
      window.localStorage.setItem(
        SELECTED_GUILD_KEY,
        JSON.stringify(normalizedGuild),
      );
    }

    try {
      const resources = await loadResources(normalizedGuild.id);
      set({ resources, loading: false, error: null });
    } catch (error) {
      const failure = error as ResourceLoadFailure;
      set({
        loading: false,
        error: failure?.message || "Could not reach the NorBot API.",
      });
    }
  },

  reload: async () => {
    set({ loading: true, error: null });

    try {
      let selected = get().selectedGuild;
      if (!selected && typeof window !== "undefined") {
        try {
          const raw = window.localStorage.getItem(SELECTED_GUILD_KEY);
          if (raw) selected = JSON.parse(raw) as SelectedGuild;
        } catch {
          selected = null;
        }
      }

      if (selected?.id) {
        const current = selected;
        try {
          const response = await fetchWithTimeout(
            apiUrl("/api/v1/sessions/servers"),
            { cache: "no-store", credentials: "include" },
            RESOURCE_TIMEOUT_MS,
          );
          if (response.ok) {
            const data = (await response.json()) as {
              servers?: Array<{
                id: string;
                name?: string;
                icon?: string | null;
                icon_url?: string | null;
                bot_installed?: boolean;
              }>;
            };
            const match = (data.servers ?? []).find(
              (server) => String(server.id) === current.id,
            );
            if (match) {
              selected = {
                id: String(match.id),
                name: String(match.name ?? current.name),
                icon: match.icon ?? current.icon ?? null,
                icon_url: resolvedGuildIcon({
                  id: String(match.id),
                  icon: match.icon ?? current.icon ?? null,
                  icon_url: match.icon_url ?? current.icon_url ?? null,
                }),
                bot_installed: Boolean(match.bot_installed),
              };
            }
          }
        } catch {
          // Keep the last stored icon/name if the refresh fails.
        }
        await get().selectGuild(selected);
        return;
      }

      const healthResponse = await fetchWithTimeout(
        apiUrl(`/bot/health`),
        { cache: "no-store", credentials: "include" },
        RESOURCE_TIMEOUT_MS,
      );
      const health = healthResponse.ok ? await healthResponse.json() : null;
      const guilds = health?.status?.guilds;

      if (!Array.isArray(guilds) || guilds.length === 0) {
        set({
          error:
            "Bot is offline or not in any server yet. Start the bot and invite it to your server first.",
          guildId: null,
          selectedGuild: null,
          resources: null,
          loading: false,
        });
        return;
      }

      const first = guilds[0] as {
        id?: unknown;
        name?: unknown;
        icon?: unknown;
        icon_url?: unknown;
      };
      const iconHash = typeof first.icon === "string" ? first.icon : null;
      const fallbackIcon =
        typeof first.icon_url === "string" ? first.icon_url : null;
      await get().selectGuild({
        id: String(first.id),
        name: String(first.name ?? "Server"),
        icon: iconHash,
        icon_url: discordIconUrl(String(first.id), iconHash) ?? fallbackIcon,
        bot_installed: true,
      });
    } catch {
      set({
        error: "Could not reach the NorBot API. Is it running on port 8000?",
        loading: false,
      });
    }
  },
}));

/** Drop-in replacement for the old useFirstGuild hook. */
export function useFirstGuild() {
  const guildId = useGuildStore((s) => s.guildId);
  const resources = useGuildStore((s) => s.resources);
  const loading = useGuildStore((s) => s.loading);
  const error = useGuildStore((s) => s.error);
  const reload = useGuildStore((s) => s.reload);
  const selectedGuild = useGuildStore((s) => s.selectedGuild);
  return { guildId, resources, loading, error, reload, selectedGuild };
}
