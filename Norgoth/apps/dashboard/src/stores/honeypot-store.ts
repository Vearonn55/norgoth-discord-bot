"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";

export type HoneypotConfig = {
  enabled: boolean;
  trap_channel_ids: string[];
  post_pinned_warning: boolean;
  warning_content: string;
  warning_embed: Record<string, unknown> | null;
  punishment: "log_only" | "delete" | "timeout" | "kick" | "kick_purge" | "ban";
  delete_history_hours: number;
  ignore_bots: boolean;
  exempt_role_ids: string[];
  exempt_member_ids: string[];
  log_channel_id: string | null;
  ping_role_id: string | null;
  timeout_minutes: number;
};

type HoneypotState = {
  config: HoneypotConfig | null;
  triggers: Record<string, unknown>[];
  triggersTotal: number;
  loading: boolean;
  saving: boolean;
  error: string | null;
  load: (guildId: string) => Promise<void>;
  save: (guildId: string, config: HoneypotConfig) => Promise<void>;
  loadTriggers: (guildId: string, offset?: number) => Promise<void>;
  requestCreateChannel: (guildId: string, name: string) => Promise<void>;
};

const defaults: HoneypotConfig = {
  enabled: false,
  trap_channel_ids: [],
  post_pinned_warning: true,
  warning_content:
    "⚠️ This channel is a honeypot trap. Do not post here. Posting will result in moderation action.",
  warning_embed: null,
  punishment: "kick",
  delete_history_hours: 0,
  ignore_bots: true,
  exempt_role_ids: [],
  exempt_member_ids: [],
  log_channel_id: null,
  ping_role_id: null,
  timeout_minutes: 60,
};

export const useHoneypotStore = create<HoneypotState>((set) => ({
  config: null,
  triggers: [],
  triggersTotal: 0,
  loading: false,
  saving: false,
  error: null,
  load: async (guildId) => {
    set({ loading: true, error: null });
    try {
      const response = await fetch(apiUrl(`/guilds/${guildId}/honeypot`), {
        cache: "no-store",
        credentials: "include",
      });
      if (!response.ok) throw new Error("Failed to load honeypot config");
      const data = await response.json();
      set({ config: { ...defaults, ...data }, loading: false });
    } catch (e) {
      set({
        loading: false,
        error: e instanceof Error ? e.message : "Load failed",
      });
    }
  },
  save: async (guildId, config) => {
    set({ saving: true, error: null });
    try {
      const response = await fetch(apiUrl(`/guilds/${guildId}/honeypot`), {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...config,
          log_channel_id: config.log_channel_id || null,
          ping_role_id: config.ping_role_id || null,
        }),
      });
      if (!response.ok) throw new Error("Failed to save honeypot config");
      const data = await response.json();
      set({ config: { ...defaults, ...data }, saving: false });
    } catch (e) {
      set({
        saving: false,
        error: e instanceof Error ? e.message : "Save failed",
      });
    }
  },
  loadTriggers: async (guildId, offset = 0) => {
    const response = await fetch(
      apiUrl(`/guilds/${guildId}/honeypot/triggers?offset=${offset}&limit=50`),
      { cache: "no-store", credentials: "include" }
    );
    if (!response.ok) return;
    const data = await response.json();
    set({ triggers: data.items ?? [], triggersTotal: data.total ?? 0 });
  },
  requestCreateChannel: async (guildId, name) => {
    await fetch(apiUrl(`/guilds/${guildId}/honeypot/create-channel`), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
  },
}));
