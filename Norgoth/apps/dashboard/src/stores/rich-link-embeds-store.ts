"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";
import { readApiError } from "@/lib/api-error";

export type RichLinkPlatforms = {
  twitter: boolean;
  bluesky: boolean;
  tiktok: boolean;
  reddit: boolean;
};

export type RichLinkRewriteHosts = {
  twitter: string;
  bluesky: string;
  tiktok: string;
  reddit: string;
};

export type RichLinkEmbedsConfig = {
  enabled: boolean;
  platforms: RichLinkPlatforms;
  channel_allowlist: string[];
  channel_denylist: string[];
  ignore_bots: boolean;
  process_edits: boolean;
  max_links_per_message: number;
  rewrite_hosts: RichLinkRewriteHosts;
  disclosure_acknowledged: boolean;
};

type RichLinkEmbedsState = {
  config: RichLinkEmbedsConfig | null;
  loading: boolean;
  saving: boolean;
  error: string | null;
  load: (guildId: string) => Promise<void>;
  save: (guildId: string, config: RichLinkEmbedsConfig) => Promise<void>;
};

export const defaults: RichLinkEmbedsConfig = {
  enabled: false,
  platforms: {
    twitter: true,
    bluesky: true,
    tiktok: true,
    reddit: true,
  },
  channel_allowlist: [],
  channel_denylist: [],
  ignore_bots: true,
  process_edits: false,
  max_links_per_message: 3,
  rewrite_hosts: {
    twitter: "fxtwitter.com",
    bluesky: "bskx.app",
    tiktok: "vxtiktok.com",
    reddit: "vxreddit.com",
  },
  disclosure_acknowledged: false,
};

const TIMEOUT_MS = 20_000;
let latestLoadRequestId = 0;

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

function normalize(data: Record<string, unknown>): RichLinkEmbedsConfig {
  const platforms = {
    ...defaults.platforms,
    ...((data.platforms as Partial<RichLinkPlatforms> | undefined) ?? {}),
  };
  const rewrite_hosts = {
    ...defaults.rewrite_hosts,
    ...((data.rewrite_hosts as Partial<RichLinkRewriteHosts> | undefined) ?? {}),
  };
  return {
    ...defaults,
    ...data,
    platforms,
    rewrite_hosts,
    channel_allowlist: Array.isArray(data.channel_allowlist)
      ? (data.channel_allowlist as string[])
      : [],
    channel_denylist: Array.isArray(data.channel_denylist)
      ? (data.channel_denylist as string[])
      : [],
  } as RichLinkEmbedsConfig;
}

export const useRichLinkEmbedsStore = create<RichLinkEmbedsState>((set) => ({
  config: null,
  loading: false,
  saving: false,
  error: null,
  load: async (guildId) => {
    const requestId = ++latestLoadRequestId;
    set({ loading: true, error: null });
    try {
      const response = await fetchWithTimeout(
        apiUrl(`/guilds/${guildId}/rich-link-embeds`),
        { cache: "no-store", credentials: "include" },
        TIMEOUT_MS,
      );
      if (!response.ok) {
        const apiError = await readApiError(response);
        throw new Error(apiError.message);
      }
      const data = (await response.json()) as Record<string, unknown>;
      if (requestId !== latestLoadRequestId) return;
      set({ config: normalize(data) });
    } catch (e) {
      if (requestId !== latestLoadRequestId) return;
      set({
        error:
          e instanceof Error
            ? e.message
            : "Failed to load Rich Link Embeds configuration.",
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
        apiUrl(`/guilds/${guildId}/rich-link-embeds`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          cache: "no-store",
          body: JSON.stringify(config),
        },
        TIMEOUT_MS,
      );
      if (!response.ok) {
        const apiError = await readApiError(response);
        throw new Error(apiError.message);
      }
      const data = (await response.json()) as Record<string, unknown>;
      set({ config: normalize(data) });
    } catch (e) {
      set({
        error:
          e instanceof Error
            ? e.message
            : "Failed to save Rich Link Embeds configuration.",
      });
      throw e;
    } finally {
      set({ saving: false });
    }
  },
}));
