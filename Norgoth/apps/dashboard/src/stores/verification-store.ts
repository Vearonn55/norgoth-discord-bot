"use client";

import { create } from "zustand";
import {
  defaultDateRange,
  type DateRangeValue,
} from "@/components/ui/date-range-filter";
import { apiUrl } from "@/lib/api";

export type VerificationConfig = {
  verification_channel_id: string;
  log_channel_id: string;
  verified_role_id: string;
  unverified_role_id: string;
  member_role_id: string;
  minimum_account_age_days: number;
  session_timeout_seconds: number;
  deny_vpn_or_proxy: boolean;
  deny_shared_ip: boolean;
  enabled: boolean;
};

export type VerificationLog = {
  id: string;
  discord_user_id: string;
  status: "success" | "failed";
  reason: string | null;
  vpn_or_proxy_detected: boolean;
  shared_ip_detected: boolean;
  blacklisted_guild_detected: boolean;
  created_at: string;
};

export const DEFAULT_VERIFICATION_CONFIG: VerificationConfig = {
  verification_channel_id: "",
  log_channel_id: "",
  verified_role_id: "",
  unverified_role_id: "",
  member_role_id: "",
  minimum_account_age_days: 7,
  session_timeout_seconds: 900,
  deny_vpn_or_proxy: true,
  deny_shared_ip: true,
  enabled: true,
};

type VerificationState = {
  config: VerificationConfig;
  configured: boolean;
  loading: boolean;
  saving: boolean;
  error: string | null;
  savedAt: string | null;
  publishing: boolean;
  publishFeedback: string | null;
  copied: boolean;
  logs: VerificationLog[];
  logsLoading: boolean;
  logsError: string | null;
  dateRange: DateRangeValue;
  setConfig: (
    config:
      | VerificationConfig
      | ((current: VerificationConfig) => VerificationConfig)
  ) => void;
  setError: (error: string | null) => void;
  setDateRange: (range: DateRangeValue) => void;
  loadConfig: (guildId: string) => Promise<void>;
  save: (guildId: string) => Promise<void>;
  publishPanel: (guildId: string) => Promise<void>;
  copyVerifyLink: (url: string) => Promise<void>;
  loadLogs: (guildId: string) => Promise<void>;
};

export const useVerificationStore = create<VerificationState>((set, get) => ({
  config: DEFAULT_VERIFICATION_CONFIG,
  configured: false,
  loading: true,
  saving: false,
  error: null,
  savedAt: null,
  publishing: false,
  publishFeedback: null,
  copied: false,
  logs: [],
  logsLoading: true,
  logsError: null,
  dateRange: defaultDateRange(7),
  setConfig: (config) =>
    set((state) => ({
      config: typeof config === "function" ? config(state.config) : config,
    })),
  setError: (error) => set({ error }),
  setDateRange: (range) => set({ dateRange: range }),
  loadConfig: async (guildId) => {
    set({ loading: true, error: null });

    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/configuration`),
        { cache: "no-store" }
      );

      if (response.ok) {
        const stored = (await response.json()) as VerificationConfig;
        set({
          config: {
            verification_channel_id: stored.verification_channel_id,
            log_channel_id: stored.log_channel_id,
            verified_role_id: stored.verified_role_id,
            unverified_role_id: stored.unverified_role_id,
            member_role_id: stored.member_role_id,
            minimum_account_age_days: stored.minimum_account_age_days,
            session_timeout_seconds: stored.session_timeout_seconds,
            deny_vpn_or_proxy: stored.deny_vpn_or_proxy,
            deny_shared_ip: stored.deny_shared_ip,
            enabled: stored.enabled,
          },
          configured: true,
        });
      }
    } catch {
      set({
        error: "Could not reach the Norgoth API. Is it running on port 8000?",
      });
    } finally {
      set({ loading: false });
    }
  },
  save: async (guildId) => {
    const { config } = get();
    const requiredFields: [keyof VerificationConfig, string][] = [
      ["verification_channel_id", "Verification channel"],
      ["log_channel_id", "Log channel"],
      ["verified_role_id", "Verified role"],
      ["unverified_role_id", "Unverified role"],
      ["member_role_id", "Member role"],
    ];

    for (const [field, label] of requiredFields) {
      if (!config[field]) {
        set({ error: `${label} is required.` });
        return;
      }
    }

    set({ saving: true, error: null });

    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/configuration`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(config),
        }
      );

      if (!response.ok) {
        const body = await response.text();
        set({
          error:
            response.status === 404
              ? "Guild is not registered yet. Make sure the bot is online (it registers the server automatically), then retry."
              : `Save failed: ${body}`,
        });
        return;
      }

      set({
        configured: true,
        savedAt: new Date().toLocaleTimeString(),
      });
    } catch {
      set({ error: "Save failed: could not reach the API." });
    } finally {
      set({ saving: false });
    }
  },
  publishPanel: async (guildId) => {
    const { config } = get();

    if (!config.verification_channel_id) {
      set({
        publishFeedback: "Choose a verification channel and save first.",
      });
      return;
    }

    set({ publishing: true, publishFeedback: null });

    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/verification/publish-panel`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            channel_id: config.verification_channel_id,
          }),
        }
      );

      const body = await response.json().catch(() => null);

      if (!response.ok) {
        const message =
          body?.error?.message ||
          body?.detail ||
          `Publish failed (HTTP ${response.status})`;
        set({ publishFeedback: String(message) });
        return;
      }

      set({
        publishFeedback:
          "Verification panel published to the verification channel.",
      });
    } catch {
      set({
        publishFeedback: "Could not reach the API to publish the panel.",
      });
    } finally {
      set({ publishing: false });
    }
  },
  copyVerifyLink: async (url) => {
    try {
      await navigator.clipboard.writeText(url);
      set({ copied: true });
      window.setTimeout(() => set({ copied: false }), 2000);
    } catch {
      set({ error: "Could not copy the link to the clipboard." });
    }
  },
  loadLogs: async (guildId) => {
    set({ logsLoading: true, logsError: null });

    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/verification-logs?limit=50`),
        { cache: "no-store" }
      );

      if (!response.ok) {
        set({
          logsError:
            response.status === 404
              ? "Guild is not registered in the verification domain yet."
              : "Could not load verification logs.",
        });
        return;
      }

      set({ logs: (await response.json()) as VerificationLog[] });
    } catch {
      set({ logsError: "Could not reach the Norgoth API." });
    } finally {
      set({ logsLoading: false });
    }
  },
}));
