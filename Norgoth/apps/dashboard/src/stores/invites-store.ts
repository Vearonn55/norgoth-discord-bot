"use client";

import { create } from "zustand";
import {
  defaultDateRange,
  type DateRangeValue,
} from "@/components/ui/date-range-filter";
import { apiUrl } from "@/lib/api";

export type InviteLeaderboardEntry = {
  rank: number;
  inviter_id: string;
  name: string;
  joins: number;
  leaves: number;
  rejoins: number;
  net: number;
};

export type RecentJoin = {
  member_id?: string | null;
  member_name: string;
  inviter_id?: string | null;
  inviter_name: string | null;
  attribution?: string | null;
  code: string | null;
  rejoin: boolean;
  joined_at: string;
  left_at: string | null;
};

type InvitesState = {
  leaderboard: InviteLeaderboardEntry[];
  recent: RecentJoin[];
  loadError: string | null;
  leaderboardSearch: string;
  leaderboardPage: number;
  recentSearch: string;
  recentPage: number;
  dateRange: DateRangeValue;
  setLeaderboardSearch: (value: string) => void;
  setLeaderboardPage: (page: number) => void;
  setRecentSearch: (value: string) => void;
  setRecentPage: (page: number) => void;
  setDateRange: (range: DateRangeValue) => void;
  load: (guildId: string) => Promise<void>;
};

export const useInvitesStore = create<InvitesState>((set) => ({
  leaderboard: [],
  recent: [],
  loadError: null,
  leaderboardSearch: "",
  leaderboardPage: 1,
  recentSearch: "",
  recentPage: 1,
  dateRange: defaultDateRange(7),
  setLeaderboardSearch: (value) =>
    set({ leaderboardSearch: value, leaderboardPage: 1 }),
  setLeaderboardPage: (page) => set({ leaderboardPage: page }),
  setRecentSearch: (value) => set({ recentSearch: value, recentPage: 1 }),
  setRecentPage: (page) => set({ recentPage: page }),
  setDateRange: (range) => set({ dateRange: range, recentPage: 1 }),
  load: async (guildId) => {
    set({ loadError: null });
    try {
      const [leaderboardResponse, recentResponse] = await Promise.all([
        fetch(apiUrl(`/guilds/${guildId}/invites/leaderboard`), {
          cache: "no-store",
        }),
        fetch(apiUrl(`/guilds/${guildId}/invites/recent?limit=50`), {
          cache: "no-store",
        }),
      ]);

      if (leaderboardResponse.ok) {
        set({
          leaderboard:
            (await leaderboardResponse.json()) as InviteLeaderboardEntry[],
        });
      }

      if (recentResponse.ok) {
        set({ recent: (await recentResponse.json()) as RecentJoin[] });
      }
    } catch {
      set({ loadError: "Could not reach the Norgoth API." });
    }
  },
}));
