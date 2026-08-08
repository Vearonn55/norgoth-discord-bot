"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";

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
  icon_url?: string | null;
  bot_installed: boolean;
};

const SELECTED_GUILD_KEY = "norgoth:selected-guild:v1";

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

async function loadResources(guildId: string): Promise<GuildResources | null> {
  const resourcesResponse = await fetch(
    apiUrl(`/guilds/${guildId}/discord-resources`),
    { cache: "no-store", credentials: "include" }
  );
  if (!resourcesResponse.ok) return null;
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
    set({
      loading: true,
      error: null,
      guildId: guild.id,
      selectedGuild: guild,
      resources: null,
    });
    if (typeof window !== "undefined") {
      window.localStorage.setItem(SELECTED_GUILD_KEY, JSON.stringify(guild));
    }
    try {
      const resources = await loadResources(guild.id);
      set({ resources, loading: false, error: resources ? null : "Could not load guild resources." });
    } catch {
      set({ loading: false, error: "Could not reach the Norgoth API." });
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
        await get().selectGuild(selected);
        return;
      }

      // Fallback: first bot guild (dev / pre-selector)
      const healthResponse = await fetch(apiUrl(`/bot/health`), {
        cache: "no-store",
        credentials: "include",
      });
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

      await get().selectGuild({
        id: String(guilds[0].id),
        name: String(guilds[0].name ?? "Server"),
        bot_installed: true,
      });
    } catch {
      set({
        error: "Could not reach the Norgoth API. Is it running on port 8000?",
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
