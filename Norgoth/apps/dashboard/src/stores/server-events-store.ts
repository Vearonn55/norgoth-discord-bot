"use client";

import { create } from "zustand";
import {
  defaultDateRange,
  type DateRangeValue,
} from "@/components/ui/date-range-filter";
import { apiUrl } from "@/lib/api";
import { createId } from "@/lib/id";

export type EventCategory = "member" | "message" | "role" | "channel";

export type EventLogEntry = {
  id: string;
  category: EventCategory;
  action: string;
  description: string;
  fields: Record<string, string>;
  actor_id?: string | null;
  actor_name?: string | null;
  created_at: string;
};

export type LoggingGroup = {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  channel_id: string | null;
  event_keys: string[];
};

export type LoggingConfig = {
  enabled: boolean;
  log_channel_id: string | null;
  member_events: boolean;
  message_events: boolean;
  role_events: boolean;
  channel_events: boolean;
  member_channel_id: string | null;
  message_channel_id: string | null;
  role_channel_id: string | null;
  channel_channel_id: string | null;
  groups: LoggingGroup[];
};

export const DEFAULT_LOGGING_CONFIG: LoggingConfig = {
  enabled: true,
  log_channel_id: null,
  member_events: true,
  message_events: true,
  role_events: true,
  channel_events: true,
  member_channel_id: null,
  message_channel_id: null,
  role_channel_id: null,
  channel_channel_id: null,
  groups: [],
};

export function newLoggingGroup(): LoggingGroup {
  return {
    id: createId(),
    name: "Custom group",
    description: "",
    enabled: true,
    channel_id: null,
    event_keys: [],
  };
}

type ServerEventsState = {
  entries: EventLogEntry[];
  category: EventCategory | "all";
  loading: boolean;
  error: string | null;
  config: LoggingConfig;
  saving: boolean;
  savedAt: string | null;
  search: string;
  eventType: string;
  page: number;
  dateRange: DateRangeValue;
  setCategory: (category: EventCategory | "all") => void;
  setConfig: (
    config: LoggingConfig | ((current: LoggingConfig) => LoggingConfig)
  ) => void;
  setSearch: (value: string) => void;
  setEventType: (value: string) => void;
  setPage: (page: number) => void;
  setDateRange: (range: DateRangeValue) => void;
  loadEvents: (guildId: string) => Promise<void>;
  loadConfig: (guildId: string) => Promise<void>;
  saveConfig: (guildId: string) => Promise<void>;
};

export const useServerEventsStore = create<ServerEventsState>((set, get) => ({
  entries: [],
  category: "all",
  loading: true,
  error: null,
  config: DEFAULT_LOGGING_CONFIG,
  saving: false,
  savedAt: null,
  search: "",
  eventType: "all",
  page: 1,
  dateRange: defaultDateRange(7),
  setCategory: (category) => set({ category, page: 1 }),
  setConfig: (config) =>
    set((state) => ({
      config: typeof config === "function" ? config(state.config) : config,
    })),
  setSearch: (value) => set({ search: value, page: 1 }),
  setEventType: (value) => set({ eventType: value, page: 1 }),
  setPage: (page) => set({ page }),
  setDateRange: (range) => set({ dateRange: range, page: 1 }),
  loadEvents: async (guildId) => {
    set({ loading: true, error: null });

    try {
      const { category } = get();
      const query = category === "all" ? "" : `&category=${category}`;
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/event-logs?limit=100${query}`),
        { cache: "no-store" }
      );

      if (!response.ok) {
        set({ error: "Could not load server events." });
        return;
      }

      set({ entries: (await response.json()) as EventLogEntry[] });
    } catch {
      set({ error: "Could not reach the Norgoth API." });
    } finally {
      set({ loading: false });
    }
  },
  loadConfig: async (guildId) => {
    try {
      const response = await fetch(apiUrl(`/guilds/${guildId}/logging`), {
        cache: "no-store",
      });

      if (response.ok) {
        const stored = (await response.json()) as Partial<LoggingConfig>;
        set((state) => ({
          config: {
            ...state.config,
            ...stored,
            groups: Array.isArray(stored.groups)
              ? stored.groups
              : state.config.groups,
          },
        }));
      }
    } catch {
      // Config panel falls back to defaults; events panel reports errors.
    }
  },
  saveConfig: async (guildId) => {
    set({ saving: true });

    try {
      const response = await fetch(apiUrl(`/guilds/${guildId}/logging`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(get().config),
      });

      if (response.ok) {
        set({ savedAt: new Date().toLocaleTimeString() });
      }
    } finally {
      set({ saving: false });
    }
  },
}));
