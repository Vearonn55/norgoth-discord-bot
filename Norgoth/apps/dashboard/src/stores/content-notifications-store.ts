"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";

export type ContentPlatform = "youtube" | "twitch" | "kick" | "x" | "tiktok";

export type PlatformAvailability = {
  platform: ContentPlatform;
  available: boolean;
  supports_push: boolean;
  reason: string | null;
  active_limit?: number;
  active_count?: number;
  active_remaining?: number;
  total_limit?: number;
  total_count?: number;
  total_remaining?: number;
};

export type PlatformUsage = {
  platform: ContentPlatform;
  active_limit: number;
  active_count: number;
  active_remaining: number;
  total_limit: number;
  total_count: number;
  total_remaining: number;
};

export type ResolvedCreator = {
  platform: ContentPlatform;
  platform_creator_id: string;
  username: string;
  display_name: string;
  profile_url: string;
  avatar_url: string | null;
  canonical_url: string | null;
  available?: boolean;
  reason?: string | null;
};

export type ContentAccount = {
  id: string;
  guild_id: string;
  source: {
    id: string;
    platform: ContentPlatform;
    platform_creator_id: string;
    username: string;
    display_name: string;
    profile_url: string;
    avatar_url: string | null;
    canonical_url: string | null;
    monitor_status: string;
    last_event_at: string | null;
  } | null;
  destination_channel_id: string;
  ping_role_id: string | null;
  template_id: string | null;
  sender_style_id: string | null;
  event_types: string[];
  enabled: boolean;
  status: string;
  last_event_at: string | null;
};

export type NotificationTemplate = {
  id: string;
  name: string;
  platform_default_for: string | null;
  content: string;
  embed_json: Record<string, unknown> | null;
};

export type SenderStyle = {
  id: string;
  display_name: string;
  avatar_url: string | null;
};

export type DeliveryHistoryItem = {
  job_id: string;
  status: string;
  attempt_count: number;
  latency_ms: number | null;
  last_error: string | null;
  created_at: string | null;
  platform: string;
  event_type: string;
  title: string | null;
  content_url: string | null;
  creator_name: string;
  destination_channel_id: string;
};

export type ContentAnalytics = {
  notifications_sent: number;
  failed_notifications: number;
  total_jobs: number;
  delivery_success_rate: number;
  average_delivery_latency_ms: number;
  platform_distribution: Array<{ platform: string; count: number }>;
  worker_online: boolean;
};

type ContentNotificationsState = {
  accounts: ContentAccount[];
  templates: NotificationTemplate[];
  styles: SenderStyle[];
  platforms: PlatformAvailability[];
  platformUsage: PlatformUsage[];
  history: DeliveryHistoryItem[];
  analytics: ContentAnalytics | null;
  workerOnline: boolean;
  loading: boolean;
  saving: boolean;
  error: string | null;
  loadAccounts: (guildId: string) => Promise<void>;
  loadTemplates: (guildId: string) => Promise<void>;
  loadStyles: (guildId: string) => Promise<void>;
  loadHistory: (guildId: string) => Promise<void>;
  loadAnalytics: (guildId: string) => Promise<void>;
  resolveAccount: (
    guildId: string,
    platform: ContentPlatform,
    url: string
  ) => Promise<ResolvedCreator>;
  createAccount: (
    guildId: string,
    payload: {
      platform: ContentPlatform;
      url: string;
      destination_channel_id: string;
      ping_role_id?: string | null;
      template_id?: string | null;
      sender_style_id?: string | null;
    }
  ) => Promise<void>;
  deleteAccount: (guildId: string, subscriptionId: string) => Promise<void>;
  toggleAccount: (
    guildId: string,
    subscriptionId: string,
    enabled: boolean
  ) => Promise<void>;
  testNotification: (guildId: string, subscriptionId: string) => Promise<void>;
  createTemplate: (
    guildId: string,
    payload: {
      name: string;
      content: string;
      platform_default_for?: string | null;
      embed_json?: Record<string, unknown> | null;
    }
  ) => Promise<void>;
  deleteTemplate: (guildId: string, templateId: string) => Promise<void>;
  createStyle: (
    guildId: string,
    payload: { display_name: string; avatar_url?: string | null }
  ) => Promise<void>;
  deleteStyle: (guildId: string, styleId: string) => Promise<void>;
};

function readApiErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}

export const useContentNotificationsStore = create<ContentNotificationsState>(
  (set, get) => ({
    accounts: [],
    templates: [],
    styles: [],
    platforms: [],
    platformUsage: [],
    history: [],
    analytics: null,
    workerOnline: false,
    loading: false,
    saving: false,
    error: null,

    async loadAccounts(guildId) {
      set({ loading: true, error: null });
      try {
        const response = await fetch(
          apiUrl(`/guilds/${guildId}/content-notifications/accounts`),
          { cache: "no-store", credentials: "include" }
        );
        if (!response.ok) throw new Error("Failed to load accounts");
        const data = await response.json();
        set({
          accounts: data.accounts ?? [],
          platforms: data.platforms ?? [],
          platformUsage: data.platform_usage ?? [],
          workerOnline: Boolean(data.worker_online),
          loading: false,
        });
      } catch (error) {
        set({
          loading: false,
          error: error instanceof Error ? error.message : "Load failed",
        });
      }
    },

    async loadTemplates(guildId) {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/content-notifications/templates`),
        { cache: "no-store", credentials: "include" }
      );
      if (!response.ok) return;
      const data = await response.json();
      set({ templates: data.templates ?? [] });
    },

    async loadStyles(guildId) {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/content-notifications/sender-styles`),
        { cache: "no-store", credentials: "include" }
      );
      if (!response.ok) return;
      const data = await response.json();
      set({ styles: data.styles ?? [] });
    },

    async loadHistory(guildId) {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/content-notifications/history?limit=100`),
        { cache: "no-store", credentials: "include" }
      );
      if (!response.ok) return;
      const data = await response.json();
      set({ history: data.items ?? [] });
    },

    async loadAnalytics(guildId) {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/content-notifications/analytics`),
        { cache: "no-store", credentials: "include" }
      );
      if (!response.ok) return;
      const data = await response.json();
      set({ analytics: data });
    },

    async resolveAccount(guildId, platform, url) {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/content-notifications/resolve`),
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ platform, url }),
        }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Could not resolve account");
      }
      return data as ResolvedCreator;
    },

    async createAccount(guildId, payload) {
      set({ saving: true, error: null });
      try {
        const response = await fetch(
          apiUrl(`/guilds/${guildId}/content-notifications/accounts`),
          {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          }
        );
        const data = await response.json();
        if (!response.ok) {
          throw new Error(readApiErrorDetail(data.detail, "Save failed"));
        }
        await get().loadAccounts(guildId);
        set({ saving: false });
      } catch (error) {
        set({
          saving: false,
          error: error instanceof Error ? error.message : "Save failed",
        });
        throw error;
      }
    },

    async deleteAccount(guildId, subscriptionId) {
      await fetch(
        apiUrl(
          `/guilds/${guildId}/content-notifications/accounts/${subscriptionId}`
        ),
        { method: "DELETE", credentials: "include" }
      );
      await get().loadAccounts(guildId);
    },

    async toggleAccount(guildId, subscriptionId, enabled) {
      const response = await fetch(
        apiUrl(
          `/guilds/${guildId}/content-notifications/accounts/${subscriptionId}`
        ),
        {
          method: "PATCH",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled }),
        }
      );
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(readApiErrorDetail(data.detail, "Update failed"));
      }
      await get().loadAccounts(guildId);
    },

    async testNotification(guildId, subscriptionId) {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/content-notifications/test`),
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ subscription_id: subscriptionId }),
        }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string" ? data.detail : "Test failed"
        );
      }
    },

    async createTemplate(guildId, payload) {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/content-notifications/templates`),
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      if (!response.ok) throw new Error("Could not create template");
      await get().loadTemplates(guildId);
    },

    async deleteTemplate(guildId, templateId) {
      await fetch(
        apiUrl(
          `/guilds/${guildId}/content-notifications/templates/${templateId}`
        ),
        { method: "DELETE", credentials: "include" }
      );
      await get().loadTemplates(guildId);
    },

    async createStyle(guildId, payload) {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/content-notifications/sender-styles`),
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      if (!response.ok) throw new Error("Could not create sender style");
      await get().loadStyles(guildId);
    },

    async deleteStyle(guildId, styleId) {
      await fetch(
        apiUrl(
          `/guilds/${guildId}/content-notifications/sender-styles/${styleId}`
        ),
        { method: "DELETE", credentials: "include" }
      );
      await get().loadStyles(guildId);
    },
  })
);
