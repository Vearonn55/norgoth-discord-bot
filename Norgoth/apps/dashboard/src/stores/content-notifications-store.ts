"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";
import { accountsListQuery, CN_PAGE_SIZE } from "@/lib/cn-url-state";

export type ContentPlatform = "youtube" | "twitch" | "kick" | "x" | "tiktok";

export type PlatformAvailability = {
  platform: ContentPlatform;
  available: boolean;
  supports_push: boolean;
  transport?: string | null;
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
  event_type_distribution?: Array<{ event_type: string; count: number }>;
  status_distribution?: Array<{ status: string; count: number }>;
  series?: Array<{ day: string; succeeded: number; failed: number }>;
  recent_failures?: Array<{
    last_error: string;
    created_at: string | null;
    platform: string;
  }>;
  range_start?: string;
  range_end?: string;
  worker_online: boolean;
};

export type LoadAccountsOptions = {
  platform?: string | null;
  limit?: number;
  offset?: number;
};

export type LoadHistoryOptions = {
  platform?: string | null;
  status?: string | null;
  limit?: number;
  offset?: number;
};

export type UpdateAccountPayload = {
  destination_channel_id?: string;
  ping_role_id?: string | null;
  template_id?: string | null;
  sender_style_id?: string | null;
  event_types?: string[];
  enabled?: boolean;
};

type ContentNotificationsState = {
  accounts: ContentAccount[];
  accountsTotal: number;
  lastAccountsQuery: LoadAccountsOptions;
  templates: NotificationTemplate[];
  styles: SenderStyle[];
  platforms: PlatformAvailability[];
  platformUsage: PlatformUsage[];
  history: DeliveryHistoryItem[];
  historyTotal: number;
  analytics: ContentAnalytics | null;
  workerOnline: boolean;
  loading: boolean;
  saving: boolean;
  error: string | null;
  loadAccounts: (guildId: string, options?: LoadAccountsOptions) => Promise<void>;
  loadTemplates: (guildId: string) => Promise<void>;
  loadStyles: (guildId: string) => Promise<void>;
  loadHistory: (guildId: string, options?: LoadHistoryOptions) => Promise<void>;
  loadAnalytics: (guildId: string, days?: number) => Promise<void>;
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
      event_types?: string[];
      enabled?: boolean;
    }
  ) => Promise<void>;
  updateAccount: (
    guildId: string,
    subscriptionId: string,
    payload: UpdateAccountPayload
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
  updateTemplate: (
    guildId: string,
    templateId: string,
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
  updateStyle: (
    guildId: string,
    styleId: string,
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

function readApiErrorCode(detail: unknown): string | null {
  if (detail && typeof detail === "object" && "code" in detail) {
    const code = (detail as { code?: unknown }).code;
    if (typeof code === "string" && code.trim()) return code;
  }
  return null;
}

export class ContentNotificationApiError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "ContentNotificationApiError";
    this.code = code;
  }
}

export const useContentNotificationsStore = create<ContentNotificationsState>(
  (set, get) => ({
    accounts: [],
    accountsTotal: 0,
    lastAccountsQuery: { limit: CN_PAGE_SIZE, offset: 0 },
    templates: [],
    styles: [],
    platforms: [],
    platformUsage: [],
    history: [],
    historyTotal: 0,
    analytics: null,
    workerOnline: false,
    loading: false,
    saving: false,
    error: null,

    async loadAccounts(guildId, options) {
      const previous = get().lastAccountsQuery;
      const query: LoadAccountsOptions = {
        platform: options?.platform ?? previous.platform,
        limit: options?.limit ?? previous.limit ?? CN_PAGE_SIZE,
        offset: options?.offset ?? previous.offset ?? 0,
      };
      set({ loading: true, error: null, lastAccountsQuery: query });
      try {
        const qs = accountsListQuery(query);
        const response = await fetch(
          apiUrl(`/guilds/${guildId}/content-notifications/accounts?${qs}`),
          { cache: "no-store", credentials: "include" }
        );
        if (!response.ok) throw new Error("Failed to load accounts");
        const data = await response.json();
        set({
          accounts: data.accounts ?? [],
          accountsTotal: Number(data.total ?? data.accounts?.length ?? 0),
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
      if (!response.ok) {
        set({ error: "Failed to load templates" });
        return;
      }
      const data = await response.json();
      set({ templates: data.templates ?? [] });
    },

    async loadStyles(guildId) {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/content-notifications/sender-styles`),
        { cache: "no-store", credentials: "include" }
      );
      if (!response.ok) {
        set({ error: "Failed to load sender styles" });
        return;
      }
      const data = await response.json();
      set({ styles: data.styles ?? [] });
    },

    async loadHistory(guildId, options) {
      const params = new URLSearchParams();
      params.set("limit", String(options?.limit ?? 50));
      params.set("offset", String(options?.offset ?? 0));
      if (options?.platform) params.set("platform", options.platform);
      if (options?.status) params.set("status", options.status);
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/content-notifications/history?${params}`),
        { cache: "no-store", credentials: "include" }
      );
      if (!response.ok) {
        set({ error: "Failed to load history" });
        return;
      }
      const data = await response.json();
      set({
        history: data.items ?? [],
        historyTotal: Number(data.total ?? data.items?.length ?? 0),
      });
    },

    async loadAnalytics(guildId, days = 30) {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/content-notifications/analytics?days=${days}`),
        { cache: "no-store", credentials: "include" }
      );
      if (!response.ok) {
        set({ error: "Failed to load analytics", analytics: null });
        return;
      }
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
        throw new ContentNotificationApiError(
          readApiErrorCode(data.detail) || "resolve_failed",
          readApiErrorDetail(data.detail, "Could not resolve account"),
        );
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

    async updateAccount(guildId, subscriptionId, payload) {
      set({ saving: true, error: null });
      try {
        const response = await fetch(
          apiUrl(
            `/guilds/${guildId}/content-notifications/accounts/${subscriptionId}`
          ),
          {
            method: "PATCH",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          }
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(readApiErrorDetail(data.detail, "Update failed"));
        }
        await get().loadAccounts(guildId);
        set({ saving: false });
      } catch (error) {
        set({
          saving: false,
          error: error instanceof Error ? error.message : "Update failed",
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

    async updateTemplate(guildId, templateId, payload) {
      const response = await fetch(
        apiUrl(
          `/guilds/${guildId}/content-notifications/templates/${templateId}`
        ),
        {
          method: "PUT",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(readApiErrorDetail(data.detail, "Update failed"));
      }
      await get().loadTemplates(guildId);
    },

    async deleteTemplate(guildId, templateId) {
      const response = await fetch(
        apiUrl(
          `/guilds/${guildId}/content-notifications/templates/${templateId}`
        ),
        { method: "DELETE", credentials: "include" }
      );
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(readApiErrorDetail(data.detail, "Delete failed"));
      }
      await get().loadTemplates(guildId);
      try {
        await get().loadAccounts(guildId);
      } catch {
        // Template list is already refreshed; accounts can retry on next page load.
      }
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
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(readApiErrorDetail(data.detail, "Could not create sender style"));
      }
      await get().loadStyles(guildId);
    },

    async updateStyle(guildId, styleId, payload) {
      const response = await fetch(
        apiUrl(
          `/guilds/${guildId}/content-notifications/sender-styles/${styleId}`
        ),
        {
          method: "PATCH",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(readApiErrorDetail(data.detail, "Could not update sender style"));
      }
      await get().loadStyles(guildId);
    },

    async deleteStyle(guildId, styleId) {
      const response = await fetch(
        apiUrl(
          `/guilds/${guildId}/content-notifications/sender-styles/${styleId}`
        ),
        { method: "DELETE", credentials: "include" }
      );
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(readApiErrorDetail(data.detail, "Delete failed"));
      }
      await get().loadStyles(guildId);
    },
  })
);
