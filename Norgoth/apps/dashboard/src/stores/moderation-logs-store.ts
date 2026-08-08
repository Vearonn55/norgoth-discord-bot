"use client";

import { create } from "zustand";
import {
  defaultDateRange,
  type DateRangeValue,
} from "@/components/ui/date-range-filter";
import { apiUrl } from "@/lib/api";

export type ModerationLogEntry = {
  action: string;
  moderator_name: string;
  target: string;
  reason: string;
  detail?: string | null;
  created_at: string;
};

type ModerationLogsState = {
  entries: ModerationLogEntry[];
  loading: boolean;
  error: string | null;
  search: string;
  page: number;
  dateRange: DateRangeValue;
  setSearch: (value: string) => void;
  setPage: (page: number) => void;
  setDateRange: (range: DateRangeValue) => void;
  load: (guildId: string) => Promise<void>;
};

export const useModerationLogsStore = create<ModerationLogsState>((set) => ({
  entries: [],
  loading: true,
  error: null,
  search: "",
  page: 1,
  dateRange: defaultDateRange(7),
  setSearch: (value) => set({ search: value, page: 1 }),
  setPage: (page) => set({ page }),
  setDateRange: (range) => set({ dateRange: range, page: 1 }),
  load: async (guildId) => {
    set({ loading: true, error: null });

    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/moderation-logs?limit=100`),
        { cache: "no-store" }
      );

      if (!response.ok) {
        set({ error: "Could not load moderation logs." });
        return;
      }

      set({ entries: (await response.json()) as ModerationLogEntry[] });
    } catch {
      set({ error: "Could not reach the Norgoth API." });
    } finally {
      set({ loading: false });
    }
  },
}));
