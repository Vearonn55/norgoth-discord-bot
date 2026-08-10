"use client";

import { create } from "zustand";
import { apiUrl, readError } from "@/lib/api";

export type FeedEmoji = {
  kind: "unicode" | "custom";
  id: string | null;
  name: string;
  animated: boolean;
  reaction: string;
};

export type FeedWindowKey = "daily" | "weekly" | "monthly" | "all_time";

export type FeedWindowConfig = {
  enabled: boolean;
  channel_id: string | null;
  norgoth_managed: boolean;
};

export type FeedConfig = {
  enabled: boolean;
  upvote_emoji: FeedEmoji;
  downvote_emoji: FeedEmoji;
  source_channel_ids: string[];
  excluded_channel_ids: string[];
  min_net_score: number;
  display_limit: number;
  refresh_interval_minutes: number;
  feed_category_id: string | null;
  last_full_sync_at?: string | null;
  exclude_bots: boolean;
  exclude_webhooks: boolean;
  exclude_threads: boolean;
  windows: Record<FeedWindowKey, FeedWindowConfig>;
  last_refresh_at?: Record<string, string>;
};

export type FeedStatus = {
  enabled: boolean;
  tracked_messages: number;
  votes_total: number;
  windows: Array<{
    key: FeedWindowKey;
    configured: boolean;
    enabled: boolean;
    channel_id: string | null;
    last_updated: string | null;
  }>;
  warnings: string[];
  top_message: {
    message_id: string;
    net_score: number;
    author_id: string;
  } | null;
  last_refresh_at: Record<string, string>;
  refresh_interval_minutes?: number;
  feed_category_id?: string | null;
  last_full_sync_at?: string | null;
  next_refresh_at?: string | null;
};

export const DEFAULT_FEED_CONFIG: FeedConfig = {
  enabled: false,
  upvote_emoji: {
    kind: "unicode",
    id: null,
    name: "👍",
    animated: false,
    reaction: "👍",
  },
  downvote_emoji: {
    kind: "unicode",
    id: null,
    name: "👎",
    animated: false,
    reaction: "👎",
  },
  source_channel_ids: [],
  excluded_channel_ids: [],
  min_net_score: 1,
  display_limit: 10,
  refresh_interval_minutes: 15,
  feed_category_id: null,
  last_full_sync_at: null,
  exclude_bots: true,
  exclude_webhooks: true,
  exclude_threads: true,
  windows: {
    daily: { enabled: false, channel_id: null, norgoth_managed: false },
    weekly: { enabled: false, channel_id: null, norgoth_managed: false },
    monthly: { enabled: false, channel_id: null, norgoth_managed: false },
    all_time: { enabled: false, channel_id: null, norgoth_managed: false },
  },
  last_refresh_at: {},
};

export const FEED_WINDOW_LABELS: Record<FeedWindowKey, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  all_time: "All-Time",
};

type FeedChannelsState = {
  config: FeedConfig | null;
  status: FeedStatus | null;
  loading: boolean;
  busy: boolean;
  error: string | null;
  feedback: string | null;
  load: (guildId: string) => Promise<void>;
  save: (guildId: string, body: FeedConfig) => Promise<FeedConfig | null>;
  setEnabled: (guildId: string, enabled: boolean) => Promise<FeedConfig | null>;
  patchWindow: (
    guildId: string,
    window: FeedWindowKey,
    patch: Partial<FeedWindowConfig>
  ) => Promise<FeedConfig | null>;
  repair: (guildId: string) => Promise<void>;
};

function base(guildId: string) {
  return `/guilds/${guildId}/feed-channels`;
}

export const useFeedChannelsStore = create<FeedChannelsState>((set) => ({
  config: null,
  status: null,
  loading: false,
  busy: false,
  error: null,
  feedback: null,

  load: async (guildId) => {
    set({ loading: true, error: null });
    try {
      const [configRes, statusRes] = await Promise.all([
        fetch(apiUrl(`${base(guildId)}/config`), { cache: "no-store" }),
        fetch(apiUrl(`${base(guildId)}/status`), { cache: "no-store" }),
      ]);
      if (!configRes.ok) {
        set({ error: await readError(configRes), config: null });
        return;
      }
      const configBody = (await configRes.json()) as {
        config: FeedConfig;
        next_refresh_at?: string;
      };
      const status = statusRes.ok
        ? ((await statusRes.json()) as FeedStatus)
        : null;
      const mergedStatus = status
        ? {
            ...status,
            next_refresh_at:
              status.next_refresh_at ?? configBody.next_refresh_at ?? null,
          }
        : null;
      set({
        config: { ...DEFAULT_FEED_CONFIG, ...configBody.config },
        status: mergedStatus,
      });
    } catch {
      set({ error: "Could not reach the Norgoth API." });
    } finally {
      set({ loading: false });
    }
  },

  save: async (guildId, body) => {
    set({ busy: true, error: null, feedback: null });
    try {
      const res = await fetch(apiUrl(`${base(guildId)}/config`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        set({ error: await readError(res) });
        return null;
      }
      const data = (await res.json()) as {
        config: FeedConfig;
        next_refresh_at?: string;
      };
      set({
        config: { ...DEFAULT_FEED_CONFIG, ...data.config },
        feedback: "Top Trending settings saved.",
      });
      // Refresh status so countdown picks up new next_refresh_at.
      const statusRes = await fetch(apiUrl(`${base(guildId)}/status`), {
        cache: "no-store",
      });
      if (statusRes.ok) {
        const status = (await statusRes.json()) as FeedStatus;
        set({
          status: {
            ...status,
            next_refresh_at:
              status.next_refresh_at ?? data.next_refresh_at ?? null,
          },
        });
      }
      return data.config;
    } catch {
      set({ error: "Could not reach the Norgoth API." });
      return null;
    } finally {
      set({ busy: false });
    }
  },

  setEnabled: async (guildId, enabled) => {
    set({ busy: true, error: null, feedback: null });
    try {
      const res = await fetch(apiUrl(`${base(guildId)}/config`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      if (!res.ok) {
        set({ error: await readError(res) });
        return null;
      }
      const data = (await res.json()) as { config: FeedConfig };
      set({
        config: data.config,
        feedback: enabled ? "Top Trending enabled." : "Top Trending disabled.",
      });
      return data.config;
    } catch {
      set({ error: "Could not reach the Norgoth API." });
      return null;
    } finally {
      set({ busy: false });
    }
  },

  patchWindow: async (guildId, window, patch) => {
    set({ busy: true, error: null, feedback: null });
    try {
      const res = await fetch(
        apiUrl(`${base(guildId)}/windows/${encodeURIComponent(window)}`),
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        }
      );
      if (!res.ok) {
        set({ error: await readError(res) });
        return null;
      }
      const data = (await res.json()) as { config: FeedConfig };
      set({ config: data.config, feedback: "Feed window updated." });
      return data.config;
    } catch {
      set({ error: "Could not reach the Norgoth API." });
      return null;
    } finally {
      set({ busy: false });
    }
  },

  repair: async (guildId) => {
    set({ busy: true, error: null, feedback: null });
    try {
      // Bypass Next rewrite proxy (30s hang-up) via dedicated long-timeout route.
      const res = await fetch(`/api/guilds/${guildId}/feed-channels/repair`, {
        method: "POST",
      });
      if (!res.ok) {
        set({ error: await readError(res) });
        return;
      }
      const data = (await res.json()) as {
        success?: boolean;
        channels_created?: number;
        messages_deleted?: number;
        messages_restored?: number;
        messages_updated?: number;
        errors?: string[];
      };
      const parts = [
        `Channels recreated: ${data.channels_created ?? 0}`,
        `Broken posts removed: ${data.messages_deleted ?? 0}`,
        `Posts restored: ${data.messages_restored ?? 0}`,
        `Posts refreshed: ${data.messages_updated ?? 0}`,
      ];
      const prefix = data.success === false
        ? "Top Trending repair finished with issues."
        : "Top Trending repaired successfully.";
      const errTail =
        data.errors && data.errors.length
          ? ` ${data.errors.slice(0, 2).join(" · ")}`
          : "";
      set({
        feedback: `${prefix} ${parts.join(" · ")}.${errTail}`,
        error:
          data.success === false && data.errors?.length
            ? data.errors[0]
            : null,
      });
      const statusRes = await fetch(apiUrl(`${base(guildId)}/status`), {
        cache: "no-store",
      });
      if (statusRes.ok) {
        set({ status: (await statusRes.json()) as FeedStatus });
      }
      const configRes = await fetch(apiUrl(`${base(guildId)}/config`), {
        cache: "no-store",
      });
      if (configRes.ok) {
        const configBody = (await configRes.json()) as { config: FeedConfig };
        set({
          config: { ...DEFAULT_FEED_CONFIG, ...configBody.config },
        });
      }
    } catch {
      set({ error: "Could not reach the Norgoth API." });
    } finally {
      set({ busy: false });
    }
  },
}));
