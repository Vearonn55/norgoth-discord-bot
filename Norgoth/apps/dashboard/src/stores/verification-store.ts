"use client";

import { create } from "zustand";
import {
  defaultDateRange,
  type DateRangeValue,
} from "@/components/ui/date-range-filter";
import { apiUrl } from "@/lib/api";
import { readApiError } from "@/lib/api-error";
import {
  type VerificationValidationIssue,
} from "@/lib/verification/validation-errors";

const FETCH_OPTS: RequestInit = {
  cache: "no-store",
  credentials: "include",
};
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
  banned_ip_match_detected: boolean;
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
    "unverified_role_id",
    "member_role_id",
  ],
};

export type { VerificationValidationIssue };
export { configUpsertPayload };

function configUpsertPayload(config: VerificationConfig): Record<string, unknown> {
  return {
    verification_channel_id: config.verification_channel_id,
    ...(config.log_channel_id ? { log_channel_id: config.log_channel_id } : {}),
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
  };
}

function extractValidationIssues(data: unknown): VerificationValidationIssue[] {
  if (!data || typeof data !== "object") return [];
  const detail = (data as { detail?: unknown }).detail;
  if (!detail || typeof detail !== "object") return [];
  const record = detail as {
    code?: unknown;
    field?: unknown;
    message?: unknown;
    issues?: unknown;
  };
  if (Array.isArray(record.issues)) {
    const issues: VerificationValidationIssue[] = [];
    for (const issue of record.issues) {
      if (!issue || typeof issue !== "object") continue;
      const row = issue as {
        code?: unknown;
        field?: unknown;
        message?: unknown;
        channel_id?: unknown;
        channel_name?: unknown;
        missing_permissions?: unknown;
        overwrite_scope?: unknown;
      };
      if (typeof row.code !== "string" || !row.code) continue;
      issues.push({
        code: row.code,
        field: typeof row.field === "string" ? row.field : null,
        message: typeof row.message === "string" ? row.message : null,
        channel_id: typeof row.channel_id === "string" ? row.channel_id : null,
        channel_name:
          typeof row.channel_name === "string" ? row.channel_name : null,
        missing_permissions: Array.isArray(row.missing_permissions)
          ? row.missing_permissions.filter(
              (item): item is string => typeof item === "string",
            )
          : null,
        overwrite_scope:
          typeof row.overwrite_scope === "string" ? row.overwrite_scope : null,
      });
    }
    return issues;
  }
  if (typeof record.code === "string" && record.code) {
    return [
      {
        code: record.code,
        field: typeof record.field === "string" ? record.field : null,
        message: typeof record.message === "string" ? record.message : null,
      },
    ];
  }
  return [];
}

function bindingFieldsChanged(
  previous: VerificationConfig,
  next: VerificationConfig,
): boolean {
  return (
    previous.verification_channel_id !== next.verification_channel_id ||
    previous.log_channel_id !== next.log_channel_id ||
    previous.unverified_role_id !== next.unverified_role_id ||
    previous.member_role_id !== next.member_role_id ||
    previous.manual_review_role_id !== next.manual_review_role_id
  );
}

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
  validationIssues: VerificationValidationIssue[] | null;
  settingsModalOpen: boolean;
  validationRequestSeq: number;
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
  setSettingsModalOpen: (open: boolean) => void;
  clearValidationFeedback: () => void;
  setDateRange: (range: DateRangeValue) => void;
  loadConfig: (guildId: string) => Promise<void>;
  save: (guildId: string) => Promise<{ ok: boolean; error?: string }>;
  validateDiscord: (guildId: string) => Promise<{ ok: boolean; error?: string }>;
  patchDetectors: (
    guildId: string,
    patch: DetectorPatch
  ) => Promise<{ ok: boolean; error?: string }>;
  applyVerificationState: (
    guildId: string,
    patch: VerificationStatePatch
  ) => Promise<{ ok: boolean; error?: string }>;
  publishPanel: (guildId: string, lang?: string) => Promise<{ ok: boolean; error?: string }>;
  saveAndPublish: (
    guildId: string,
    lang?: string
  ) => Promise<{ ok: boolean; error?: string }>;
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
  validationIssues: null,
  settingsModalOpen: false,
  validationRequestSeq: 0,
  savedAt: null,
  publishing: false,
  publishFeedback: null,
  copied: false,
  logs: [],
  logsLoading: true,
  logsError: null,
  dateRange: defaultDateRange(7),
  setConfig: (config) =>
    set((state) => {
      const next =
        typeof config === "function" ? config(state.config) : config;
      return {
        config: next,
        ...(bindingFieldsChanged(state.config, next)
          ? { validationIssues: null, error: null }
          : {}),
      };
    }),
  setError: (error) => set({ error }),
  setSettingsModalOpen: (open) =>
    set((state) => ({
      settingsModalOpen: open,
      validationRequestSeq: open
        ? state.validationRequestSeq
        : state.validationRequestSeq + 1,
      ...(open ? {} : { validationIssues: null }),
    })),
  clearValidationFeedback: () => set({ validationIssues: null, error: null }),
  setDateRange: (range) => set({ dateRange: range }),
  loadConfig: async (guildId) => {
    set((state) => ({
      loading: true,
      error: null,
      validationRequestSeq: state.validationRequestSeq + 1,
    }));

    try {
      const [configResponse, setupResponse] = await Promise.all([
        fetch(apiUrl(`/api/v1/guilds/${guildId}/configuration`), FETCH_OPTS),
        fetch(
          apiUrl(`/api/v1/guilds/${guildId}/configuration/setup`),
          FETCH_OPTS,
        ),
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
      ["unverified_role_id", "Unverified role"],
      ["member_role_id", "Base member role"],
    ];

    for (const [field, label] of requiredFields) {
      if (!config[field]) {
        const issues: VerificationValidationIssue[] = [
          {
            code: "verification_setup_incomplete",
            field: String(field),
            message: null,
          },
        ];
        set({ validationIssues: issues, error: null });
        return { ok: false, error: `${label} is required.` };
      }
    }

    const saveSeq = get().validationRequestSeq + 1;
    set({
      saving: true,
      error: null,
      validationIssues: null,
      validationRequestSeq: saveSeq,
    });

    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/configuration`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(configUpsertPayload(config)),
        }
      );

      if (get().validationRequestSeq !== saveSeq) {
        return { ok: false };
      }

      if (!response.ok) {
        const raw = await response.json().catch(() => null);
        const issues = extractValidationIssues(raw);
        const apiError = await readApiError(
          new Response(JSON.stringify(raw), { status: response.status }),
        );
        const message =
          response.status === 404
            ? "Guild is not registered yet. Make sure the bot is online (it registers the server automatically), then retry."
            : apiError.message;
        set({
          validationIssues: issues.length ? issues : null,
          error: issues.length ? null : message,
        });
        return { ok: false, error: message };
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
        validationIssues: null,
        error: null,
      });
      return { ok: true };
    } catch {
      const message = "Save failed: could not reach the API.";
      set({ error: message });
      return { ok: false, error: message };
    } finally {
      set({ saving: false });
    }
  },
  validateDiscord: async (guildId) => {
    const { config } = get();
    if (!hasRequiredBindings(config)) {
      const issues: VerificationValidationIssue[] = [
        { code: "verification_setup_incomplete", field: null, message: null },
      ];
      set({ validationIssues: issues, error: null });
      return { ok: false, error: "Required bindings missing." };
    }

    const validateSeq = get().validationRequestSeq + 1;
    set({
      validating: true,
      error: null,
      validationIssues: null,
      validationRequestSeq: validateSeq,
    });

    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/configuration/validate`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(configUpsertPayload(config)),
        }
      );

      if (get().validationRequestSeq !== validateSeq) {
        return { ok: false };
      }

      if (!response.ok) {
        const raw = await response.json().catch(() => null);
        const issues = extractValidationIssues(raw);
        const apiError = await readApiError(
          new Response(JSON.stringify(raw), { status: response.status }),
        );
        set({
          validationIssues: issues.length
            ? issues
            : [{ code: apiError.code, field: null, message: apiError.message }],
          error: null,
        });
        return { ok: false, error: apiError.message };
      }

      const body = (await response.json()) as {
        ok?: boolean;
        issues?: VerificationValidationIssue[];
        setup_state?: VerificationSetupState;
      };

      if (get().validationRequestSeq !== validateSeq) {
        return { ok: false };
      }

      if (!body?.ok) {
        const issues = Array.isArray(body?.issues) ? body.issues : [];
        set({
          config: {
            ...get().config,
            setup_state: body?.setup_state ?? "degraded",
          },
          configured: false,
          validationIssues: issues.length
            ? issues
            : [{ code: "validationUnexpected", field: null, message: null }],
          error: null,
        });
        return { ok: false, error: "Discord validation failed." };
      }

      set({
        config: {
          ...get().config,
          setup_state: body?.setup_state ?? get().config.setup_state,
        },
        validationIssues: null,
        error: null,
      });
      return { ok: true };
    } catch {
      if (get().validationRequestSeq !== validateSeq) {
        return { ok: false };
      }
      set({
        validationIssues: [
          { code: "guild_metadata_unavailable", field: null, message: null },
        ],
        error: null,
      });
      return { ok: false, error: "Could not reach the NorBot API." };
    } finally {
      if (get().validationRequestSeq === validateSeq) {
        set({ validating: false });
      }
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
          credentials: "include",
          body: JSON.stringify(patch),
        }
      );

      if (!response.ok) {
        set({ config: previous });
        const apiError = await readApiError(response);
        const message =
          response.status === 404
            ? "Guild configuration not found. Configure verification first."
            : apiError.message;
        return { ok: false, error: message };
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
          credentials: "include",
          body: JSON.stringify(patch),
        }
      );

      if (!response.ok) {
        set({ config: previous });
        const apiError = await readApiError(response);
        const message =
          apiError.requestId != null
            ? `${apiError.message} (Support reference: ${apiError.requestId})`
            : apiError.message;
        return { ok: false, error: message };
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
  publishPanel: async (guildId, lang = "en") => {
    const { config } = get();

    if (!canPublishOrCopy(config)) {
      const message =
        "Save verification channels and roles before publishing the Discord panel.";
      set({ publishFeedback: message, error: message });
      return { ok: false, error: message };
    }

    set({ publishing: true, publishFeedback: null, error: null });

    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/verification/publish-panel`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            channel_id: config.verification_channel_id,
            lang,
          }),
        }
      );

      if (!response.ok) {
        const apiError = await readApiError(response);
        set({ publishFeedback: apiError.message, error: apiError.message });
        return { ok: false, error: apiError.message };
      }

      const body = (await response.json().catch(() => null)) as {
        updated?: boolean;
      } | null;

      const message = body?.updated
        ? "Verification panel updated in the verification channel."
        : "Verification panel published to the verification channel.";
      set({ publishFeedback: message });
      return { ok: true };
    } catch {
      const message = "Could not reach the API to publish the panel.";
      set({ publishFeedback: message, error: message });
      return { ok: false, error: message };
    } finally {
      set({ publishing: false });
    }
  },
  saveAndPublish: async (guildId, lang = "en") => {
    const saved = await get().save(guildId);
    if (!saved.ok) return saved;
    return get().publishPanel(guildId, lang);
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
        FETCH_OPTS,
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





