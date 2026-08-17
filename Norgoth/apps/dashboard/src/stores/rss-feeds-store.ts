"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";
import { readApiError, type ApiErrorBody } from "@/lib/api-error";

export type RssFeed = {
  id: string;
  guild_id: string;
  feed_url: string;
  display_name: string | null;
  channel_id: string;
  mention_role_id: string | null;
  enabled: boolean;
  poll_interval_seconds: number;
  format_hint: string | null;
  next_poll_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  failure_count: number;
  created_at: string | null;
  updated_at: string | null;
};

export type RssProbeResult = {
  ok: boolean;
  error: string | null;
  error_code?: string | null;
  format_hint: string | null;
  feed_title: string | null;
  sample_title: string | null;
  item_count: number;
  final_url: string | null;
};

export type CreateRssFeedInput = {
  feed_url: string;
  channel_id: string;
  mention_role_id?: string | null;
  display_name?: string | null;
  poll_interval_seconds?: number;
  enabled?: boolean;
};

export type PatchRssFeedInput = {
  channel_id?: string;
  mention_role_id?: string | null;
  clear_mention_role?: boolean;
  display_name?: string | null;
  poll_interval_seconds?: number;
  enabled?: boolean;
  feed_url?: string;
};

type RssFeedsState = {
  feeds: RssFeed[];
  maxFeeds: number;
  workerOnline: boolean;
  loading: boolean;
  saving: boolean;
  error: string | null;
  load: (guildId: string) => Promise<void>;
  create: (guildId: string, input: CreateRssFeedInput) => Promise<RssFeed>;
  update: (
    guildId: string,
    feedId: string,
    input: PatchRssFeedInput,
  ) => Promise<RssFeed>;
  remove: (guildId: string, feedId: string) => Promise<void>;
  probe: (guildId: string, feedUrl: string) => Promise<RssProbeResult>;
};

const TIMEOUT_MS = 30_000;
let latestLoadId = 0;

function errorWithCode(apiError: ApiErrorBody): Error {
  const error = new Error(apiError.message);
  (error as Error & { code?: string }).code = apiError.code;
  return error;
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

export const useRssFeedsStore = create<RssFeedsState>((set) => ({
  feeds: [],
  maxFeeds: 15,
  workerOnline: false,
  loading: false,
  saving: false,
  error: null,
  load: async (guildId) => {
    const requestId = ++latestLoadId;
    set({ loading: true, error: null });
    try {
      const response = await fetchWithTimeout(
        apiUrl(`/guilds/${guildId}/rss-feeds`),
        { cache: "no-store", credentials: "include" },
        TIMEOUT_MS,
      );
      if (!response.ok) {
        const apiError = await readApiError(response);
        throw errorWithCode(apiError);
      }
      const data = (await response.json()) as {
        feeds: RssFeed[];
        max_feeds?: number;
        worker_online?: boolean;
      };
      if (requestId !== latestLoadId) return;
      set({
        feeds: data.feeds ?? [],
        maxFeeds: data.max_feeds ?? 15,
        workerOnline: Boolean(data.worker_online),
      });
    } catch (e) {
      if (requestId !== latestLoadId) return;
      set({
        error:
          e instanceof Error ? e.message : "Failed to load RSS feeds.",
      });
    } finally {
      if (requestId === latestLoadId) set({ loading: false });
    }
  },
  create: async (guildId, input) => {
    set({ saving: true, error: null });
    try {
      const response = await fetchWithTimeout(
        apiUrl(`/guilds/${guildId}/rss-feeds`),
        {
          method: "POST",
          credentials: "include",
          cache: "no-store",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(input),
        },
        TIMEOUT_MS,
      );
      if (!response.ok) {
        const apiError = await readApiError(response);
        throw errorWithCode(apiError);
      }
      const feed = (await response.json()) as RssFeed;
      set((state) => ({ feeds: [feed, ...state.feeds] }));
      return feed;
    } catch (e) {
      const message =
        e instanceof Error ? e.message : "Failed to create RSS feed.";
      set({ error: message });
      throw e;
    } finally {
      set({ saving: false });
    }
  },
  update: async (guildId, feedId, input) => {
    set({ saving: true, error: null });
    try {
      const response = await fetchWithTimeout(
        apiUrl(`/guilds/${guildId}/rss-feeds/${feedId}`),
        {
          method: "PATCH",
          credentials: "include",
          cache: "no-store",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(input),
        },
        TIMEOUT_MS,
      );
      if (!response.ok) {
        const apiError = await readApiError(response);
        throw errorWithCode(apiError);
      }
      const feed = (await response.json()) as RssFeed;
      set((state) => ({
        feeds: state.feeds.map((f) => (f.id === feedId ? feed : f)),
      }));
      return feed;
    } catch (e) {
      const message =
        e instanceof Error ? e.message : "Failed to update RSS feed.";
      set({ error: message });
      throw e;
    } finally {
      set({ saving: false });
    }
  },
  remove: async (guildId, feedId) => {
    set({ saving: true, error: null });
    try {
      const response = await fetchWithTimeout(
        apiUrl(`/guilds/${guildId}/rss-feeds/${feedId}`),
        {
          method: "DELETE",
          credentials: "include",
          cache: "no-store",
        },
        TIMEOUT_MS,
      );
      if (!response.ok) {
        const apiError = await readApiError(response);
        throw errorWithCode(apiError);
      }
      set((state) => ({
        feeds: state.feeds.filter((f) => f.id !== feedId),
      }));
    } catch (e) {
      const message =
        e instanceof Error ? e.message : "Failed to delete RSS feed.";
      set({ error: message });
      throw e;
    } finally {
      set({ saving: false });
    }
  },
  probe: async (guildId, feedUrl) => {
    const response = await fetchWithTimeout(
      apiUrl(`/guilds/${guildId}/rss-feeds/probe`),
      {
        method: "POST",
        credentials: "include",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feed_url: feedUrl }),
      },
      TIMEOUT_MS,
    );
    if (!response.ok) {
      const apiError = await readApiError(response);
      throw errorWithCode(apiError);
    }
    return (await response.json()) as RssProbeResult;
  },
}));
