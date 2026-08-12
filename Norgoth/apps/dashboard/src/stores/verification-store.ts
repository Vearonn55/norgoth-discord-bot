"use client";

import { create } from "zustand";
import {
  defaultDateRange,
  type DateRangeValue,
} from "@/components/ui/date-range-filter";
import { apiUrl } from "@/lib/api";

export type RiskAction = "deny" | "manual_review";

export type VerificationSetupState =
  | "not_configured"
  | "incomplete"
  | "disabled"
  | "active"
  | "degraded"
  | "error";

export type VerificationConfig = {
  verification_channel_id: string;
  log_channel_id: string;
  unverified_role_id: string;
  member_role_id: string;
  manual_review_role_id: string;
  minimum_account_age_days: number;
  session_timeout_seconds: number;
  deny_vpn_or_proxy: boolean;
  deny_shared_ip: boolean;
  vpn_or_proxy_action: RiskAction;
  shared_ip_action: RiskAction;
  enabled: boolean;
  setup_state?: VerificationSetupState;
  missing_bindings?: string[];
};

export type DetectorPatch = Partial<
  Pick<
    VerificationConfig,
    | "deny_vpn_or_proxy"
    | "vpn_or_proxy_action"
    | "deny_shared_ip"
    | "shared_ip_action"
  >
>;

export type VerificationStatePatch = Partial<
  Pick<VerificationConfig, "enabled" | "deny_vpn_or_proxy" | "deny_shared_ip">
>;

/**
 * Mirror of the backend state machine so the master + detector toggles feel
 * instant before the normalized server response arrives. The single source of
 * truth remains the backend; this is optimistic-only.
 */
export function deriveVerificationState(
  current: VerificationConfig,
  patch: VerificationStatePatch
): Pick<VerificationConfig, "enabled" | "deny_vpn_or_proxy" | "deny_shared_ip"> {
  let enabled = current.enabled;
  let vpn = current.deny_vpn_or_proxy;
  let shared = current.deny_shared_ip;

  if (patch.enabled !== undefined) {
    enabled = vpn = shared = patch.enabled;
  } else {
    if (patch.deny_vpn_or_proxy !== undefined) vpn = patch.deny_vpn_or_proxy;
    if (patch.deny_shared_ip !== undefined) shared = patch.deny_shared_ip;
    enabled = vpn || shared;
  }

  if (enabled && !vpn && !shared) {
    return { enabled: false, deny_vpn_or_proxy: false, deny_shared_ip: false };
  }
  return { enabled, deny_vpn_or_proxy: vpn, deny_shared_ip: shared };
}

export function hasRequiredBindings(config: VerificationConfig): boolean {
  return Boolean(
    config.verification_channel_id &&
      config.log_channel_id &&
      config.unverified_role_id &&
      config.member_role_id
  );
}

export function canPublishOrCopy(config: VerificationConfig): boolean {
  const state = config.setup_state;
  // Only allow after required bindings are persisted (server setup states).
  if (state === "active" || state === "disabled" || state === "degraded") {
    return hasRequiredBindings(config);
  }
  return false;
}

export type VerificationLog = {
  id: string;
  discord_user_id: string;
  display_name: string | null;
  username: string | null;
  avatar_url: string | null;
  status: "success" | "failed" | "manual_review";
  reason: string | null;
  vpn_or_proxy_detected: boolean;
  shared_ip_detected: boolean;
  high_risk_guild_detected: boolean;
  matched_high_risk_guild_ids: string[];
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
};

export type VerificationLogListResponse = {
  items: VerificationLog[];
  total: number;
};

export const DEFAULT_VERIFICATION_CONFIG: VerificationConfig = {
  verification_channel_id: "",
  log_channel_id: "",
  unverified_role_id: "",
  member_role_id: "",
  manual_review_role_id: "",
  minimum_account_age_days: 7,
  session_timeout_seconds: 900,
  deny_vpn_or_proxy: true,
  deny_shared_ip: true,
  vpn_or_proxy_action: "deny",
  shared_ip_action: "deny",
  enabled: false,
  setup_state: "not_configured",
  missing_bindings: [
    "verification_channel_id",
    "log_channel_id",
    "unverified_role_id",
    "member_role_id",
  ],
};

function mapStoredConfig(stored: VerificationConfig): VerificationConfig {
  return {
    verification_channel_id: stored.verification_channel_id ?? "",
    log_channel_id: stored.log_channel_id ?? "",
    unverified_role_id: stored.unverified_role_id ?? "",
    member_role_id: stored.member_role_id ?? "",
    manual_review_role_id: stored.manual_review_role_id ?? "",
    minimum_account_age_days: stored.minimum_account_age_days,
    session_timeout_seconds: stored.session_timeout_seconds,
    deny_vpn_or_proxy: stored.deny_vpn_or_proxy,
    deny_shared_ip: stored.deny_shared_ip,
    vpn_or_proxy_action: stored.vpn_or_proxy_action ?? "deny",
    shared_ip_action: stored.shared_ip_action ?? "deny",
    enabled: stored.enabled,
    setup_state: stored.setup_state,
    missing_bindings: stored.missing_bindings ?? [],
  };
}

type VerificationState = {
  config: VerificationConfig;
  configured: boolean;
  loading: boolean;
  saving: boolean;
  validating: boolean;
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
  validateDiscord: (guildId: string) => Promise<{ ok: boolean; error?: string }>;
  patchDetectors: (
    guildId: string,
    patch: DetectorPatch
  ) => Promise<{ ok: boolean; error?: string }>;
  applyVerificationState: (
    guildId: string,
    patch: VerificationStatePatch
  ) => Promise<{ ok: boolean; error?: string }>;
  publishPanel: (guildId: string) => Promise<void>;
  copyVerifyLink: (url: string) => Promise<void>;
  loadLogs: (guildId: string) => Promise<void>;
};

export const useVerificationStore = create<VerificationState>((set, get) => ({
  config: DEFAULT_VERIFICATION_CONFIG,
  configured: false,
  loading: true,
  saving: false,
  validating: false,
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
      const [configResponse, setupResponse] = await Promise.all([
        fetch(apiUrl(`/api/v1/guilds/${guildId}/configuration`), {
          cache: "no-store",
        }),
        fetch(apiUrl(`/api/v1/guilds/${guildId}/configuration/setup`), {
          cache: "no-store",
        }),
      ]);

      let setupState: VerificationSetupState = "not_configured";
      let missing: string[] = DEFAULT_VERIFICATION_CONFIG.missing_bindings ?? [];
      if (setupResponse.ok) {
        const setup = (await setupResponse.json()) as {
          setup_state?: VerificationSetupState;
          missing_bindings?: string[];
        };
        setupState = setup.setup_state ?? "not_configured";
        missing = setup.missing_bindings ?? [];
      }

      if (configResponse.ok) {
        const stored = (await configResponse.json()) as VerificationConfig;
        const mapped = mapStoredConfig(stored);
        set({
          config: {
            ...mapped,
            setup_state: mapped.setup_state ?? setupState,
            missing_bindings: mapped.missing_bindings?.length
              ? mapped.missing_bindings
              : missing,
          },
          configured:
            (mapped.setup_state ?? setupState) === "active" ||
            (mapped.setup_state ?? setupState) === "disabled" ||
            ((mapped.setup_state ?? setupState) === "degraded" &&
              hasRequiredBindings(mapped)),
        });
      } else if (configResponse.status === 404) {
        set({
          config: {
            ...DEFAULT_VERIFICATION_CONFIG,
            setup_state: setupState,
            missing_bindings: missing,
          },
          configured: false,
        });
      }
    } catch {
      set({
        error: "Could not reach the NorBot API. Is it running on port 8000?",
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
      ["unverified_role_id", "Unverified role"],
      ["member_role_id", "Base member role"],
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
          body: JSON.stringify({
            verification_channel_id: config.verification_channel_id,
            log_channel_id: config.log_channel_id,
            unverified_role_id: config.unverified_role_id,
            member_role_id: config.member_role_id,
            manual_review_role_id: config.manual_review_role_id,
            minimum_account_age_days: config.minimum_account_age_days,
            session_timeout_seconds: config.session_timeout_seconds,
            deny_vpn_or_proxy: config.deny_vpn_or_proxy,
            deny_shared_ip: config.deny_shared_ip,
            vpn_or_proxy_action: config.vpn_or_proxy_action,
            shared_ip_action: config.shared_ip_action,
            enabled: config.enabled,
          }),
        }
      );

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        const detail = body?.detail;
        const message =
          typeof detail === "object" && detail?.message
            ? String(detail.message)
            : typeof detail === "string"
              ? detail
              : await response.text().catch(() => "");
        set({
          error:
            response.status === 404
              ? "Guild is not registered yet. Make sure the bot is online (it registers the server automatically), then retry."
              : `Save failed: ${message || `HTTP ${response.status}`}`,
        });
        return;
      }

      const stored = (await response.json()) as VerificationConfig;
      const mapped = mapStoredConfig(stored);
      set({
        config: mapped,
        configured:
          mapped.setup_state === "active" ||
          mapped.setup_state === "disabled" ||
          mapped.setup_state === "degraded",
        savedAt: new Date().toLocaleTimeString(),
      });
    } catch {
      set({ error: "Save failed: could not reach the API." });
    } finally {
      set({ saving: false });
    }
  },
  validateDiscord: async (guildId) => {
    set({ validating: true, error: null });
    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/configuration/validate`),
        { method: "POST" }
      );
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        const message =
          body?.detail?.message ||
          body?.detail ||
          `Validate failed (HTTP ${response.status})`;
        set({ error: String(message) });
        return { ok: false, error: String(message) };
      }
      if (!body?.ok) {
        const issue = Array.isArray(body?.issues) ? body.issues[0] : null;
        const message = issue?.message || "Discord validation failed.";
        set({
          config: {
            ...get().config,
            setup_state: body?.setup_state ?? "degraded",
          },
          configured: false,
          error: String(message),
        });
        return { ok: false, error: String(message) };
      }
      set({
        config: {
          ...get().config,
          setup_state: body?.setup_state ?? get().config.setup_state,
        },
        error: null,
      });
      return { ok: true };
    } catch {
      set({ error: "Could not reach the NorBot API to validate Discord." });
      return { ok: false, error: "Could not reach the NorBot API." };
    } finally {
      set({ validating: false });
    }
  },
  patchDetectors: async (guildId, patch) => {
    const previous = get().config;
    set({ config: { ...previous, ...patch } });

    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/configuration/detectors`),
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        }
      );

      if (!response.ok) {
        set({ config: previous });
        const body = await response.json().catch(() => null);
        const message =
          response.status === 404
            ? "Guild configuration not found. Configure verification first."
            : body?.error?.message ||
              body?.detail ||
              `Update failed (HTTP ${response.status})`;
        return { ok: false, error: String(message) };
      }

      const stored = (await response.json()) as VerificationConfig;
      set((state) => ({
        config: {
          ...state.config,
          ...mapStoredConfig({ ...state.config, ...stored }),
        },
      }));
      return { ok: true };
    } catch {
      set({ config: previous });
      return { ok: false, error: "Could not reach the NorBot API." };
    }
  },
  applyVerificationState: async (guildId, patch) => {
    const previous = get().config;
    const optimistic = deriveVerificationState(previous, patch);
    set({ config: { ...previous, ...optimistic } });

    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/configuration/state`),
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        }
      );

      if (!response.ok) {
        set({ config: previous });
        const body = await response.json().catch(() => null);
        const message =
          body?.error?.message ||
          body?.detail ||
          `Update failed (HTTP ${response.status})`;
        return { ok: false, error: String(message) };
      }

      const stored = (await response.json()) as VerificationConfig;
      set((state) => ({
        config: mapStoredConfig({ ...state.config, ...stored }),
      }));
      return { ok: true };
    } catch {
      set({ config: previous });
      return { ok: false, error: "Could not reach the NorBot API." };
    }
  },
  publishPanel: async (guildId) => {
    const { config } = get();

    if (!canPublishOrCopy(config)) {
      set({
        publishFeedback:
          "Save verification channels and roles before publishing the Discord panel.",
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
          body?.detail?.message ||
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
    if (!canPublishOrCopy(get().config)) {
      set({
        error:
          "Save verification channels and roles before copying the public link.",
      });
      return;
    }
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

      const data = (await response.json()) as VerificationLogListResponse;
      set({ logs: data.items });
    } catch {
      set({ logsError: "Could not reach the NorBot API." });
    } finally {
      set({ logsLoading: false });
    }
  },
}));





