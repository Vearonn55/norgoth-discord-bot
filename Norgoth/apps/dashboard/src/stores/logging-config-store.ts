"use client";

import { create } from "zustand";
import { apiUrl, readError } from "@/lib/api";
import { colorToHex, hexToColor } from "@/lib/logging";

export { colorToHex, hexToColor };

export type LoggingEventDef = { event_type: string; label: string };
export type LoggingGroupDef = {
  key: string;
  label: string;
  default_color: number | null;
  events: LoggingEventDef[];
};
export type LoggingCatalog = { groups: LoggingGroupDef[] };

export type LoggingChannelConfig = {
  id?: string;
  key: string;
  name: string;
  channel_id: string | null;
  norgoth_managed: boolean;
  default_color: number | null;
  position: number;
  /** Category gate; defaults true for legacy payloads. */
  enabled: boolean;
};

export type LoggingEventConfig = {
  event_type: string;
  channel_key: string | null;
  color: number | null;
  enabled: boolean;
};

export type LoggingConfig = {
  id: string;
  guild_id: string;
  enabled: boolean;
  status: "draft" | "active";
  category_id: string | null;
  category_name: string | null;
  norgoth_managed_category: boolean;
  channels: LoggingChannelConfig[];
  events: LoggingEventConfig[];
};

export type LoggingConfigBody = {
  enabled: boolean;
  category_id: string | null;
  category_name: string | null;
  norgoth_managed_category: boolean;
  channels: Omit<LoggingChannelConfig, "id">[];
  events: LoggingEventConfig[];
};

export type LoggingChannelHealth = {
  key: string;
  status: "ok" | "missing" | "error" | "unprovisioned";
  channel_id?: string;
  error?: string;
};

export type LoggingHealth = {
  healthy: boolean;
  category_status: string;
  channels: LoggingChannelHealth[];
};

/**
 * Resolve a stable display label for a logging channel row.
 *
 * Preference order: the live Discord channel name, then the persisted config
 * name, then a diagnostic. The raw Discord ID is NEVER used as a label — this
 * is what previously made names "turn into IDs" after rapid toggling when the
 * live guild-resources cache didn't include a freshly reconciled channel.
 */
export function resolveChannelLabel(
  channel: Pick<LoggingChannelConfig, "channel_id" | "name">,
  liveChannels: ReadonlyArray<{ id: string; name: string }>
): string {
  const live = channel.channel_id
    ? liveChannels.find((c) => c.id === channel.channel_id)?.name
    : undefined;
  if (live) return `#${live}`;
  const persisted = channel.name?.trim();
  // Guard against legacy corrupted rows where the name was overwritten by an ID.
  if (persisted && persisted !== channel.channel_id) return `#${persisted}`;
  return channel.channel_id ? "Unknown channel" : "Not provisioned";
}


type LoggingConfigState = {
  config: LoggingConfig | null;
  catalog: LoggingCatalog | null;
  health: LoggingHealth | null;
  loading: boolean;
  busy: boolean;
  error: string | null;
  feedback: string | null;
  load: (guildId: string) => Promise<void>;
  loadCatalog: (guildId: string) => Promise<void>;
  setEnabled: (guildId: string, enabled: boolean) => Promise<LoggingConfig | null>;
  setChannelEnabled: (
    guildId: string,
    channelKey: string,
    enabled: boolean
  ) => Promise<LoggingConfig | null>;
  save: (
    guildId: string,
    body: LoggingConfigBody
  ) => Promise<LoggingConfig | null>;
  updateChannel: (
    guildId: string,
    channelKey: string,
    channelPatch: Partial<Pick<LoggingChannelConfig, "name" | "default_color">>,
    channelEvents: LoggingEventConfig[]
  ) => Promise<LoggingConfig | null>;
  deleteDiscordChannel: (
    guildId: string,
    channelKey: string
  ) => Promise<LoggingConfig | null>;
  provision: (guildId: string) => Promise<LoggingConfig | null>;
  reconcile: (guildId: string) => Promise<LoggingHealth | null>;
  repair: (guildId: string) => Promise<LoggingConfig | null>;
  reset: (guildId: string, deleteDiscord: boolean) => Promise<boolean>;
};

function base(guildId: string): string {
  return `/guilds/${guildId}/logging`;
}

function normalizeLoggingConfig(config: LoggingConfig): LoggingConfig {
  return {
    ...config,
    channels: (config.channels ?? []).map((channel) => ({
      ...channel,
      enabled: channel.enabled !== false,
    })),
  };
}

// Guards against rapid enable/disable toggling: a single in-flight PATCH at a
// time (extra clicks are ignored) plus a sequence number so a slow, stale
// response can never overwrite the state produced by a newer request.
let toggleInFlight = false;
let toggleSeq = 0;

export const useLoggingConfigStore = create<LoggingConfigState>((set, get) => ({
  config: null,
  catalog: null,
  health: null,
  loading: false,
  busy: false,
  error: null,
  feedback: null,

  load: async (guildId) => {
    set({ loading: true, error: null });
    try {
      const [configRes, catalogRes] = await Promise.all([
        fetch(apiUrl(`${base(guildId)}/config`), { cache: "no-store" }),
        fetch(apiUrl(`${base(guildId)}/event-types`), { cache: "no-store" }),
      ]);
      if (configRes.ok) {
        const body = (await configRes.json()) as { config: LoggingConfig | null };
        set({
          config: body.config ? normalizeLoggingConfig(body.config) : null,
        });
      }
      if (catalogRes.ok) {
        set({ catalog: (await catalogRes.json()) as LoggingCatalog });
      }
    } catch {
      set({ error: "Could not reach the NorBot API." });
    } finally {
      set({ loading: false });
    }
  },

  loadCatalog: async (guildId) => {
    try {
      const res = await fetch(apiUrl(`${base(guildId)}/event-types`), {
        cache: "no-store",
      });
      if (res.ok) set({ catalog: (await res.json()) as LoggingCatalog });
    } catch {
      /* ignore */
    }
  },

  setEnabled: async (guildId, enabled) => {
    // Ignore rapid repeat toggles while one is still resolving. The backend
    // PATCH is idempotent, but this keeps the UI authoritative and prevents
    // request storms.
    if (toggleInFlight) return null;
    toggleInFlight = true;
    const seq = ++toggleSeq;
    set({ busy: true, error: null, feedback: null });
    try {
      const res = await fetch(apiUrl(`${base(guildId)}/config`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      if (seq !== toggleSeq) return null; // a newer toggle superseded this one
      if (!res.ok) {
        set({ error: await readError(res) });
        return null;
      }
      const data = (await res.json()) as { config: LoggingConfig };
      set({
        config: normalizeLoggingConfig(data.config),
        feedback: enabled ? "Logging enabled." : "Logging disabled.",
      });
      return data.config;
    } catch {
      if (seq === toggleSeq) set({ error: "Could not reach the NorBot API." });
      return null;
    } finally {
      toggleInFlight = false;
      set({ busy: false });
    }
  },

  setChannelEnabled: async (guildId, channelKey, enabled) => {
    set({ busy: true, error: null, feedback: null });
    try {
      const res = await fetch(
        apiUrl(`${base(guildId)}/channels/${encodeURIComponent(channelKey)}`),
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled }),
        }
      );
      if (!res.ok) {
        set({ error: await readError(res) });
        return null;
      }
      const data = (await res.json()) as { config: LoggingConfig };
      set({
        config: normalizeLoggingConfig(data.config),
        feedback: enabled
          ? "Category enabled."
          : "Category disabled (settings kept).",
      });
      return data.config;
    } catch {
      set({ error: "Could not reach the NorBot API." });
      return null;
    } finally {
      set({ busy: false });
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
      const data = (await res.json()) as { config: LoggingConfig };
      set({ config: data.config, feedback: "Logging configuration saved." });
      return data.config;
    } catch {
      set({ error: "Could not reach the NorBot API." });
      return null;
    } finally {
      set({ busy: false });
    }
  },

  updateChannel: async (guildId, channelKey, channelPatch, channelEvents) => {
    const current = get().config;
    if (!current) return null;

    // May be absent when configuring a catalog category omitted during setup.
    const target = current.channels.find((channel) => channel.key === channelKey);
    const name = channelPatch.name ?? target?.name;
    if (!name) {
      set({ error: "Channel name is required." });
      return null;
    }
    const default_color =
      channelPatch.default_color !== undefined
        ? channelPatch.default_color
        : (target?.default_color ?? null);

    set({ busy: true, error: null, feedback: null });
    try {
      const res = await fetch(
        apiUrl(`${base(guildId)}/channels/${encodeURIComponent(channelKey)}`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            default_color,
            events: channelEvents.map((event) => ({
              ...event,
              channel_key: channelKey,
            })),
          }),
        }
      );
      if (!res.ok) {
        set({ error: await readError(res) });
        return null;
      }
      const data = (await res.json()) as { config: LoggingConfig };
      const saved = normalizeLoggingConfig(data.config);
      set({
        config: saved,
        feedback: "Category settings saved.",
      });

      // Provision only fills in channels lacking a Discord id.
      const needsProvision = saved.channels.some(
        (channel) => channel.norgoth_managed && !channel.channel_id
      );
      if (needsProvision) {
        return get().provision(guildId);
      }
      return saved;
    } catch {
      set({ error: "Could not reach the NorBot API." });
      return null;
    } finally {
      set({ busy: false });
    }
  },

  deleteDiscordChannel: async (guildId, channelKey) => {
    set({ busy: true, error: null, feedback: null });
    try {
      const res = await fetch(
        apiUrl(
          `${base(guildId)}/channels/${encodeURIComponent(channelKey)}/discord-channel`
        ),
        { method: "DELETE" }
      );
      if (!res.ok) {
        set({ error: await readError(res) });
        return null;
      }
      const data = (await res.json()) as { config: LoggingConfig };
      set({
        config: normalizeLoggingConfig(data.config),
        feedback: "Log channel deleted; category disabled.",
      });
      return normalizeLoggingConfig(data.config);
    } catch {
      set({ error: "Could not reach the NorBot API." });
      return null;
    } finally {
      set({ busy: false });
    }
  },

  provision: async (guildId) => {
    set({ busy: true, error: null, feedback: null });
    try {
      const res = await fetch(apiUrl(`${base(guildId)}/provision`), {
        method: "POST",
      });
      if (!res.ok) {
        set({ error: await readError(res) });
        return null;
      }
      const data = (await res.json()) as { config: LoggingConfig };
      set({ config: data.config, feedback: "Logging channels provisioned." });
      return data.config;
    } catch {
      set({ error: "Could not reach the NorBot API." });
      return null;
    } finally {
      set({ busy: false });
    }
  },

  reconcile: async (guildId) => {
    set({ busy: true, error: null });
    try {
      const res = await fetch(apiUrl(`${base(guildId)}/reconcile`), {
        method: "POST",
      });
      if (!res.ok) {
        set({ error: await readError(res) });
        return null;
      }
      const health = (await res.json()) as LoggingHealth;
      set({ health });
      return health;
    } catch {
      set({ error: "Could not reach the NorBot API." });
      return null;
    } finally {
      set({ busy: false });
    }
  },

  repair: async (guildId) => {
    set({ busy: true, error: null, feedback: null });
    try {
      const res = await fetch(apiUrl(`${base(guildId)}/repair`), {
        method: "POST",
      });
      if (!res.ok) {
        set({ error: await readError(res) });
        return null;
      }
      const data = (await res.json()) as { config: LoggingConfig };
      set({ config: data.config, feedback: "Repair complete." });
      return data.config;
    } catch {
      set({ error: "Could not reach the NorBot API." });
      return null;
    } finally {
      set({ busy: false });
    }
  },

  reset: async (guildId, deleteDiscord) => {
    set({ busy: true, error: null, feedback: null });
    try {
      const res = await fetch(
        apiUrl(
          `${base(guildId)}/config?delete_discord_resources=${deleteDiscord}`
        ),
        { method: "DELETE" }
      );
      if (!res.ok) {
        set({ error: await readError(res) });
        return false;
      }
      set({ config: null, health: null, feedback: "Logging configuration reset." });
      return true;
    } catch {
      set({ error: "Could not reach the NorBot API." });
      return false;
    } finally {
      set({ busy: false });
    }
  },
}));
