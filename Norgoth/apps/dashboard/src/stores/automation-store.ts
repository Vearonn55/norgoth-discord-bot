"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";
import { createId } from "@/lib/id";

// ── Welcome / auto-role / mod-log settings ──────────────────────────────────

export type AutomationConfig = {
  welcome_enabled: boolean;
  welcome_channel_id: string | null;
  welcome_message: string;
  leave_enabled: boolean;
  leave_channel_id: string | null;
  leave_message: string;
  auto_role_enabled: boolean;
  auto_role_id: string | null;
  auto_role_ids: string[];
  mod_log_channel_id: string | null;
};

export type WelcomeStatus = {
  ok: boolean;
  reason: string;
  member?: string | null;
  channel_id?: string | null;
  attempted_at?: string;
} | null;

export const DEFAULT_AUTOMATION_CONFIG: AutomationConfig = {
  welcome_enabled: false,
  welcome_channel_id: null,
  welcome_message: "Welcome to {server}, {user}!",
  leave_enabled: false,
  leave_channel_id: null,
  leave_message: "{username} has left {server}.",
  auto_role_enabled: false,
  auto_role_id: null,
  auto_role_ids: [],
  mod_log_channel_id: null,
};

function apiErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;

  const record = payload as Record<string, unknown>;
  const nested = record.error;

  if (nested && typeof nested === "object") {
    const message = (nested as Record<string, unknown>).message;
    if (typeof message === "string" && message.trim()) return message;
  }

  if (typeof record.detail === "string" && record.detail.trim()) {
    return record.detail;
  }

  return fallback;
}

export type AutomationSection = "welcome" | "leave";

type AutomationSettingsState = {
  config: AutomationConfig;
  /** Last persisted baseline used for per-section dirty detection + partial saves. */
  savedConfig: AutomationConfig;
  welcomeStatus: WelcomeStatus;
  loading: boolean;
  saving: boolean;
  savingSection: AutomationSection | null;
  testing: boolean;
  dirty: boolean;
  editorSeed: number;
  error: string | null;
  savedAt: string | null;
  testResult: string | null;
  testError: string | null;
  leaveTesting: boolean;
  leaveTestResult: string | null;
  leaveTestError: string | null;
  setConfig: (
    config: AutomationConfig | ((current: AutomationConfig) => AutomationConfig)
  ) => void;
  updateConfig: (
    updater: (current: AutomationConfig) => AutomationConfig
  ) => void;
  load: (guildId: string) => Promise<void>;
  save: (guildId: string) => Promise<void>;
  /**
   * Saves only the fields for one section (welcome or leave), merged onto the
   * last saved baseline, so unsaved edits in the other section are preserved.
   */
  saveSection: (guildId: string, section: AutomationSection) => Promise<void>;
  sendTestWelcome: (guildId: string) => Promise<void>;
  sendTestLeave: (guildId: string) => Promise<void>;
};

function sectionPatch(
  config: AutomationConfig,
  section: AutomationSection
): Partial<AutomationConfig> {
  return section === "welcome"
    ? {
        welcome_enabled: config.welcome_enabled,
        welcome_channel_id: config.welcome_channel_id,
        welcome_message: config.welcome_message,
      }
    : {
        leave_enabled: config.leave_enabled,
        leave_channel_id: config.leave_channel_id,
        leave_message: config.leave_message,
      };
}

export const useAutomationStore = create<AutomationSettingsState>(
  (set, get) => ({
    config: DEFAULT_AUTOMATION_CONFIG,
    savedConfig: DEFAULT_AUTOMATION_CONFIG,
    welcomeStatus: null,
    loading: true,
    saving: false,
    savingSection: null,
    testing: false,
    dirty: false,
    editorSeed: 0,
    error: null,
    savedAt: null,
    testResult: null,
    testError: null,
    leaveTesting: false,
    leaveTestResult: null,
    leaveTestError: null,
    setConfig: (config) =>
      set((state) => ({
        config: typeof config === "function" ? config(state.config) : config,
      })),
    updateConfig: (updater) =>
      set((state) => ({
        config: updater(state.config),
        dirty: true,
      })),
    load: async (guildId) => {
      set({ loading: true, error: null });

      try {
        const [configResponse, statusResponse] = await Promise.all([
          fetch(apiUrl(`/guilds/${guildId}/automation`), {
            cache: "no-store",
          }),
          fetch(apiUrl(`/guilds/${guildId}/automation/status`), {
            cache: "no-store",
          }),
        ]);

        if (configResponse.ok) {
          const stored = (await configResponse.json()) as AutomationConfig;
          const merged = {
            ...DEFAULT_AUTOMATION_CONFIG,
            ...stored,
            auto_role_ids:
              Array.isArray(stored.auto_role_ids) && stored.auto_role_ids.length
                ? stored.auto_role_ids
                : stored.auto_role_id
                  ? [stored.auto_role_id]
                  : [],
          };
          set((state) => ({
            config: merged,
            savedConfig: merged,
            dirty: false,
            editorSeed: state.editorSeed + 1,
          }));
        }

        if (statusResponse.ok) {
          const statusPayload = await statusResponse.json();
          set({ welcomeStatus: statusPayload?.welcome ?? null });
        }
      } catch {
        set({
          error:
            "Could not reach the Norgoth API. Is it running on port 8000?",
        });
      } finally {
        set({ loading: false });
      }
    },
    save: async (guildId) => {
      set({ saving: true, error: null });

      try {
        const response = await fetch(apiUrl(`/guilds/${guildId}/automation`), {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(get().config),
        });

        if (!response.ok) {
          const payload = await response.json().catch(() => null);
          set({
            error: `Save failed: ${apiErrorMessage(payload, await response.text())}`,
          });
          return;
        }

        set((state) => ({
          savedConfig: state.config,
          dirty: false,
          savedAt: new Date().toLocaleTimeString(),
        }));
      } catch {
        set({ error: "Save failed: could not reach the API." });
      } finally {
        set({ saving: false });
      }
    },
    saveSection: async (guildId, section) => {
      set({ saving: true, savingSection: section, error: null });

      try {
        const { config, savedConfig } = get();
        const patch = sectionPatch(config, section);
        const payload = { ...savedConfig, ...patch };

        const response = await fetch(apiUrl(`/guilds/${guildId}/automation`), {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          const errPayload = await response.json().catch(() => null);
          set({
            error: `Save failed: ${apiErrorMessage(errPayload, await response.text())}`,
          });
          return;
        }

        set((state) => {
          const nextSaved = { ...state.savedConfig, ...patch };
          return {
            savedConfig: nextSaved,
            // Global dirty stays true if the other section still differs.
            dirty: JSON.stringify(state.config) !== JSON.stringify(nextSaved),
            savedAt: new Date().toLocaleTimeString(),
          };
        });
      } catch {
        set({ error: "Save failed: could not reach the API." });
      } finally {
        set({ saving: false, savingSection: null });
      }
    },
    sendTestWelcome: async (guildId) => {
      const { config } = get();

      if (!config.welcome_channel_id) {
        set({ testError: "Pick a welcome channel first, then try again." });
        return;
      }

      set({
        testing: true,
        testResult: null,
        testError: null,
        error: null,
      });

      try {
        // Persist only the welcome fields (with welcome enabled) so unsaved
        // leave-message edits are not written by the test action.
        const welcomePatch = {
          ...sectionPatch(config, "welcome"),
          welcome_enabled: true,
        };
        const payload = { ...get().savedConfig, ...welcomePatch };
        const saveResponse = await fetch(
          apiUrl(`/guilds/${guildId}/automation`),
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          }
        );

        if (!saveResponse.ok) {
          const payload = await saveResponse.json().catch(() => null);
          set({
            error: `Save failed: ${apiErrorMessage(payload, await saveResponse.text())}`,
            testError: "Could not save settings before sending the test.",
          });
          return;
        }

        set((state) => {
          const nextConfig = { ...state.config, welcome_enabled: true };
          const nextSaved = { ...state.savedConfig, ...welcomePatch };
          return {
            config: nextConfig,
            savedConfig: nextSaved,
            dirty: JSON.stringify(nextConfig) !== JSON.stringify(nextSaved),
            savedAt: new Date().toLocaleTimeString(),
          };
        });

        const response = await fetch(
          apiUrl(`/guilds/${guildId}/automation/test-welcome`),
          { method: "POST" }
        );

        const testPayload = await response.json().catch(() => null);

        if (!response.ok) {
          set({
            testError: apiErrorMessage(
              testPayload,
              "Test message could not be sent."
            ),
          });
          return;
        }

        set({
          testResult:
            "Test welcome message sent. Check the channel in Discord.",
        });

        const statusResponse = await fetch(
          apiUrl(`/guilds/${guildId}/automation/status`),
          { cache: "no-store" }
        );
        if (statusResponse.ok) {
          const statusPayload = await statusResponse.json();
          set({ welcomeStatus: statusPayload?.welcome ?? null });
        }
      } catch {
        set({ testError: "Could not reach the API for the test send." });
      } finally {
        set({ testing: false });
      }
    },
    sendTestLeave: async (guildId) => {
      const { config } = get();

      if (!config.leave_channel_id && !config.welcome_channel_id) {
        set({
          leaveTestError:
            "Pick a leave (or welcome) channel first, then try again.",
        });
        return;
      }

      set({
        leaveTesting: true,
        leaveTestResult: null,
        leaveTestError: null,
        error: null,
      });

      try {
        // Persist only the leave fields (with leave enabled) so unsaved
        // welcome-message edits are not written by the test action.
        const leavePatch = {
          ...sectionPatch(config, "leave"),
          leave_enabled: true,
        };
        const payload = { ...get().savedConfig, ...leavePatch };
        const saveResponse = await fetch(
          apiUrl(`/guilds/${guildId}/automation`),
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          }
        );

        if (!saveResponse.ok) {
          const errPayload = await saveResponse.json().catch(() => null);
          set({
            error: `Save failed: ${apiErrorMessage(errPayload, await saveResponse.text())}`,
            leaveTestError: "Could not save settings before sending the test.",
          });
          return;
        }

        set((state) => {
          const nextConfig = { ...state.config, leave_enabled: true };
          const nextSaved = { ...state.savedConfig, ...leavePatch };
          return {
            config: nextConfig,
            savedConfig: nextSaved,
            dirty: JSON.stringify(nextConfig) !== JSON.stringify(nextSaved),
            savedAt: new Date().toLocaleTimeString(),
          };
        });

        const response = await fetch(
          apiUrl(`/guilds/${guildId}/automation/test-leave`),
          { method: "POST" }
        );

        const testPayload = await response.json().catch(() => null);

        if (!response.ok) {
          set({
            leaveTestError: apiErrorMessage(
              testPayload,
              "Test message could not be sent."
            ),
          });
          return;
        }

        set({
          leaveTestResult:
            "Test leave message sent. Check the channel in Discord.",
        });
      } catch {
        set({ leaveTestError: "Could not reach the API for the test send." });
      } finally {
        set({ leaveTesting: false });
      }
    },
  })
);

// ── Auto-responses ──────────────────────────────────────────────────────────

export type MatchType = "exact" | "contains" | "starts_with";

export type AutoResponseRule = {
  id: string;
  enabled: boolean;
  trigger: string;
  match_type: MatchType;
  response: string;
  channel_id: string | null;
  cooldown_seconds: number;
};

export function newAutoResponseRule(): AutoResponseRule {
  return {
    id: createId(),
    enabled: true,
    trigger: "",
    match_type: "contains",
    response: "",
    channel_id: null,
    cooldown_seconds: 10,
  };
}

type AutoResponsesState = {
  rules: AutoResponseRule[];
  draft: AutoResponseRule;
  saving: boolean;
  feedback: string | null;
  feedbackIsError: boolean;
  search: string;
  page: number;
  setDraft: (
    draft: AutoResponseRule | ((current: AutoResponseRule) => AutoResponseRule)
  ) => void;
  setSearch: (value: string) => void;
  setPage: (page: number) => void;
  setFeedback: (feedback: string | null, isError?: boolean) => void;
  load: (guildId: string) => Promise<void>;
  persist: (guildId: string, nextRules: AutoResponseRule[]) => Promise<boolean>;
  addRule: (guildId: string) => Promise<void>;
};

export const useAutoResponsesStore = create<AutoResponsesState>((set, get) => ({
  rules: [],
  draft: newAutoResponseRule(),
  saving: false,
  feedback: null,
  feedbackIsError: false,
  search: "",
  page: 1,
  setDraft: (draft) =>
    set((state) => ({
      draft: typeof draft === "function" ? draft(state.draft) : draft,
    })),
  setSearch: (value) => set({ search: value, page: 1 }),
  setPage: (page) => set({ page }),
  setFeedback: (feedback, isError = false) =>
    set({ feedback, feedbackIsError: isError }),
  load: async (guildId) => {
    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/auto-responses`),
        { cache: "no-store" }
      );

      if (response.ok) {
        const body = (await response.json()) as { rules: AutoResponseRule[] };
        set({ rules: body.rules ?? [] });
      }
    } catch {
      set({
        feedback: "Could not reach the Norgoth API.",
        feedbackIsError: true,
      });
    }
  },
  persist: async (guildId, nextRules) => {
    set({ saving: true, feedback: null });

    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/auto-responses`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rules: nextRules }),
        }
      );

      if (!response.ok) {
        set({
          feedback: `Save failed: ${await response.text()}`,
          feedbackIsError: true,
        });
        return false;
      }

      set({
        rules: nextRules,
        feedback: `Rules saved at ${new Date().toLocaleTimeString()}.`,
        feedbackIsError: false,
      });
      return true;
    } catch {
      set({
        feedback: "Save failed: could not reach the API.",
        feedbackIsError: true,
      });
      return false;
    } finally {
      set({ saving: false });
    }
  },
  addRule: async (guildId) => {
    const { draft, rules, persist } = get();

    if (!draft.trigger.trim() || !draft.response.trim()) {
      set({
        feedback: "A trigger and a response are both required.",
        feedbackIsError: true,
      });
      return;
    }

    if (rules.length >= 50) {
      set({
        feedback: "Rule limit reached (50).",
        feedbackIsError: true,
      });
      return;
    }

    const saved = await persist(guildId, [
      ...rules,
      {
        ...draft,
        trigger: draft.trigger.trim(),
        response: draft.response.trim(),
      },
    ]);

    if (saved) {
      set({ draft: newAutoResponseRule() });
    }
  },
}));

// ── Role menus ──────────────────────────────────────────────────────────────

export type RoleMenuEntry = {
  role_id: string;
  label: string;
  mode: "toggle" | "give" | "take";
  style?: "primary" | "secondary" | "success" | "danger";
  emoji?: string;
};

export type RoleMenu = {
  id: string;
  title: string;
  description: string;
  channel_id: string | null;
  interaction: "buttons" | "select" | "reactions";
  roles: RoleMenuEntry[];
  published_at: string | null;
  message_id?: string | null;
};

export function newRoleMenu(): RoleMenu {
  return {
    id: createId(),
    title: "Choose your roles",
    description: "Use the controls below to manage your roles.",
    channel_id: null,
    interaction: "buttons",
    roles: [],
    published_at: null,
    message_id: null,
  };
}

type RoleMenusState = {
  menus: RoleMenu[];
  editing: RoleMenu | null;
  busy: boolean;
  feedback: string | null;
  feedbackIsError: boolean;
  setEditing: (
    editing: RoleMenu | null | ((current: RoleMenu | null) => RoleMenu | null)
  ) => void;
  setFeedback: (feedback: string | null, isError?: boolean) => void;
  load: (guildId: string) => Promise<void>;
  persist: (guildId: string, nextMenus: RoleMenu[]) => Promise<boolean>;
  saveEditing: (guildId: string) => Promise<void>;
  publish: (guildId: string, menu: RoleMenu) => Promise<void>;
  deleteMenu: (guildId: string, menu: RoleMenu) => Promise<boolean>;
};

export const useRoleMenusStore = create<RoleMenusState>((set, get) => ({
  menus: [],
  editing: null,
  busy: false,
  feedback: null,
  feedbackIsError: false,
  setEditing: (editing) =>
    set((state) => ({
      editing:
        typeof editing === "function" ? editing(state.editing) : editing,
    })),
  setFeedback: (feedback, isError = false) =>
    set({ feedback, feedbackIsError: isError }),
  load: async (guildId) => {
    try {
      const response = await fetch(apiUrl(`/guilds/${guildId}/role-menus`), {
        cache: "no-store",
      });

      if (response.ok) {
        const body = (await response.json()) as { menus: RoleMenu[] };
        set({
          menus: (body.menus ?? []).map((menu) => ({
            ...menu,
            interaction: menu.interaction ?? "buttons",
            roles: (menu.roles ?? []).map((role) => ({
              ...role,
              mode: role.mode ?? "toggle",
              style: role.style ?? "secondary",
              emoji: role.emoji ?? "",
            })),
          })),
        });
      }
    } catch {
      set({
        feedback: "Could not reach the Norgoth API.",
        feedbackIsError: true,
      });
    }
  },
  persist: async (guildId, nextMenus) => {
    set({ busy: true, feedback: null });

    try {
      const response = await fetch(apiUrl(`/guilds/${guildId}/role-menus`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ menus: nextMenus }),
      });

      if (!response.ok) {
        set({
          feedback: `Save failed: ${await response.text()}`,
          feedbackIsError: true,
        });
        return false;
      }

      set({
        menus: nextMenus,
        feedback: `Menus saved at ${new Date().toLocaleTimeString()}.`,
        feedbackIsError: false,
      });
      return true;
    } catch {
      set({
        feedback: "Save failed: could not reach the API.",
        feedbackIsError: true,
      });
      return false;
    } finally {
      set({ busy: false });
    }
  },
  saveEditing: async (guildId) => {
    const { editing, menus, persist } = get();
    if (!editing) return;

    if (!editing.title.trim()) {
      set({
        feedback: "The menu needs a title.",
        feedbackIsError: true,
      });
      return;
    }

    const exists = menus.some((menu) => menu.id === editing.id);
    const nextMenus = exists
      ? menus.map((menu) => (menu.id === editing.id ? editing : menu))
      : [...menus, editing];

    const saved = await persist(guildId, nextMenus);

    if (saved) {
      set({ editing: null });
    }
  },
  publish: async (guildId, menu) => {
    set({ busy: true, feedback: null });

    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/role-menus/${menu.id}/publish`),
        { method: "POST" }
      );

      if (response.ok) {
        set({
          feedback: `"${menu.title}" published to Discord.`,
          feedbackIsError: false,
        });
        await get().load(guildId);
      } else {
        const body = await response.json().catch(() => null);
        set({
          feedback: `Publish failed: ${body?.detail ?? `HTTP ${response.status}`}`,
          feedbackIsError: true,
        });
      }
    } catch {
      set({
        feedback: "Publish failed: could not reach the API.",
        feedbackIsError: true,
      });
    } finally {
      set({ busy: false });
    }
  },
  deleteMenu: async (guildId, menu) => {
    set({ busy: true, feedback: null });

    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/role-menus/${menu.id}`),
        { method: "DELETE" }
      );

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        set({
          feedback: `Delete failed: ${body?.detail ?? `HTTP ${response.status}`}`,
          feedbackIsError: true,
        });
        return false;
      }

      const body = (await response.json().catch(() => null)) as {
        menus?: RoleMenu[];
        discord_deleted?: boolean;
      } | null;
      const remaining =
        body?.menus ?? get().menus.filter((item) => item.id !== menu.id);
      set({
        menus: remaining,
        feedback: body?.discord_deleted
          ? `"${menu.title}" deleted, including its published message.`
          : `"${menu.title}" deleted.`,
        feedbackIsError: false,
      });
      return true;
    } catch {
      set({
        feedback: "Delete failed: could not reach the API.",
        feedbackIsError: true,
      });
      return false;
    } finally {
      set({ busy: false });
    }
  },
}));

// ── Notifications ───────────────────────────────────────────────────────────

export type NotificationPlatform = "youtube" | "twitch";

export type NotificationCreator = {
  id: string;
  enabled: boolean;
  platform: NotificationPlatform;
  handle: string;
  display_name: string;
  channel_id: string | null;
  role_id: string | null;
  message: string;
};

export function newNotificationCreator(): NotificationCreator {
  return {
    id: createId(),
    enabled: true,
    platform: "youtube",
    handle: "",
    display_name: "",
    channel_id: null,
    role_id: null,
    message: "",
  };
}

type NotificationsState = {
  creators: NotificationCreator[];
  twitchConfigured: boolean;
  draft: NotificationCreator;
  busy: boolean;
  feedback: string | null;
  feedbackIsError: boolean;
  setDraft: (
    draft:
      | NotificationCreator
      | ((current: NotificationCreator) => NotificationCreator)
  ) => void;
  setFeedback: (feedback: string | null, isError?: boolean) => void;
  load: (guildId: string) => Promise<void>;
  persist: (
    guildId: string,
    nextCreators: NotificationCreator[]
  ) => Promise<boolean>;
  addCreator: (guildId: string) => Promise<void>;
};

export const useNotificationsStore = create<NotificationsState>((set, get) => ({
  creators: [],
  twitchConfigured: false,
  draft: newNotificationCreator(),
  busy: false,
  feedback: null,
  feedbackIsError: false,
  setDraft: (draft) =>
    set((state) => ({
      draft: typeof draft === "function" ? draft(state.draft) : draft,
    })),
  setFeedback: (feedback, isError = false) =>
    set({ feedback, feedbackIsError: isError }),
  load: async (guildId) => {
    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/notifications`),
        { cache: "no-store" }
      );

      if (response.ok) {
        const body = (await response.json()) as {
          creators: NotificationCreator[];
          twitch_configured: boolean;
        };
        set({
          creators: body.creators ?? [],
          twitchConfigured: body.twitch_configured,
        });
      }
    } catch {
      set({
        feedback: "Could not reach the Norgoth API.",
        feedbackIsError: true,
      });
    }
  },
  persist: async (guildId, nextCreators) => {
    set({ busy: true, feedback: null });

    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/notifications`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ creators: nextCreators }),
        }
      );

      if (!response.ok) {
        set({
          feedback: `Save failed: ${await response.text()}`,
          feedbackIsError: true,
        });
        return false;
      }

      const body = (await response.json()) as {
        creators: NotificationCreator[];
      };
      set({
        creators: body.creators ?? nextCreators,
        feedback: `Saved at ${new Date().toLocaleTimeString()}.`,
        feedbackIsError: false,
      });
      return true;
    } catch {
      set({
        feedback: "Save failed: could not reach the API.",
        feedbackIsError: true,
      });
      return false;
    } finally {
      set({ busy: false });
    }
  },
  addCreator: async (guildId) => {
    const { draft, creators, persist } = get();

    if (!draft.handle.trim() || !draft.channel_id) {
      set({
        feedback:
          "A creator handle and an announcement channel are both required.",
        feedbackIsError: true,
      });
      return;
    }

    const saved = await persist(guildId, [
      ...creators,
      { ...draft, handle: draft.handle.trim() },
    ]);

    if (saved) {
      set({ draft: newNotificationCreator() });
    }
  },
}));
