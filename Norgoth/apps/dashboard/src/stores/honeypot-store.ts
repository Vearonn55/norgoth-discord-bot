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

const HONEYPOT_TIMEOUT_MS = 20_000;

let latestLoadRequestId = 0;
let latestTriggerRequestId = 0;

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

function errorMessage(status: number): string {
  if (status === 401) return "Your session expired. Sign in again.";
  if (status === 403) return "You do not have access to this server.";
  if (status === 404) return "Honeypot configuration is not available for this server yet.";
  if (status === 429) return "Server is temporarily rate-limited. Please retry shortly.";
  if (status >= 500) return "Server error while loading honeypot configuration.";
  return `Failed to load honeypot config (HTTP ${status}).`;
}

export const useHoneypotStore = create<HoneypotState>((set) => ({
  config: null,
  triggers: [],
  triggersTotal: 0,
  loading: false,
  saving: false,
  error: null,
  load: async (guildId) => {
    const requestId = ++latestLoadRequestId;
    set({ loading: true, error: null });
    try {
      const response = await fetchWithTimeout(
        apiUrl(`/guilds/${guildId}/honeypot`),
        { cache: "no-store", credentials: "include" },
        HONEYPOT_TIMEOUT_MS,
      );
      if (!response.ok) {
        throw new Error(errorMessage(response.status));
      }
      const data = await response.json();
      if (requestId !== latestLoadRequestId) return;
      set({ config: { ...defaults, ...data } });
    } catch (e) {
      if (requestId !== latestLoadRequestId) return;
      set({
        error:
          e instanceof Error
            ? e.message
            : "Honeypot load failed.",
      });
    } finally {
      if (requestId === latestLoadRequestId) {
        set({ loading: false });
      }
    }
  },
  save: async (guildId, config) => {
    set({ saving: true, error: null });
    try {
      const response = await fetchWithTimeout(
        apiUrl(`/guilds/${guildId}/honeypot`),
        {
          method: "PUT",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...config,
            log_channel_id: config.log_channel_id || null,
            ping_role_id: config.ping_role_id || null,
          }),
        },
        HONEYPOT_TIMEOUT_MS,
      );
      if (!response.ok) throw new Error(`Failed to save honeypot config (HTTP ${response.status}).`);
      const data = await response.json();
      set({ config: { ...defaults, ...data } });
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : "Save failed",
      });
    } finally {
      set({ saving: false });
    }
  },
  loadTriggers: async (guildId, offset = 0) => {
    const requestId = ++latestTriggerRequestId;
    try {
      const response = await fetchWithTimeout(
        apiUrl(`/guilds/${guildId}/honeypot/triggers?offset=${offset}&limit=50`),
        { cache: "no-store", credentials: "include" },
        HONEYPOT_TIMEOUT_MS,
      );
      if (!response.ok) return;
      const data = await response.json();
      if (requestId !== latestTriggerRequestId) return;
      set({ triggers: data.items ?? [], triggersTotal: data.total ?? 0 });
    } catch {
      // Optional surface: keep existing trigger list if loading fails.
    }
  },
  requestCreateChannel: async (guildId, name) => {
    try {
      await fetchWithTimeout(
        apiUrl(`/guilds/${guildId}/honeypot/create-channel`),
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        },
        HONEYPOT_TIMEOUT_MS,
      );
    } catch {
      set({ error: "Could not create the honeypot channel right now. Please retry." });
    }
  },
}));
