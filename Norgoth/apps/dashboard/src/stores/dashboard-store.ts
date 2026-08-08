"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";
import type {
  EngagementRange,
  EngagementResponse,
} from "@/lib/analytics/engagement";

export type CampaignActivity = {
  id: string;
  campaign_id: string;
  campaign_title: string;
  type: string;
  message: string;
  sent_count: number;
  failed_count: number;
  audience_count: number;
  created_at: string;
};

type DashboardState = {
  activities: CampaignActivity[];
  loading: boolean;
  loadActivity: () => Promise<void>;

  engagement: EngagementResponse | null;
  engagementRange: EngagementRange;
  engagementLoading: boolean;
  setEngagementRange: (range: EngagementRange) => void;
  loadEngagement: (guildId: string, range?: EngagementRange) => Promise<void>;
};

export const useDashboardStore = create<DashboardState>((set, get) => ({
  activities: [],
  loading: true,
  loadActivity: async () => {
    try {
      const response = await fetch(apiUrl(`/campaigns/activity`), {
        method: "GET",
        cache: "no-store",
      });

      if (!response.ok) {
        set({ activities: [], loading: false });
        return;
      }

      const data = await response.json();
      set({
        activities: Array.isArray(data) ? data.slice(0, 20) : [],
        loading: false,
      });
    } catch {
      set({ activities: [], loading: false });
    }
  },

  engagement: null,
  engagementRange: 7,
  engagementLoading: false,
  setEngagementRange: (range) => set({ engagementRange: range }),
  loadEngagement: async (guildId, range) => {
    const resolved = range ?? get().engagementRange;
    set({ engagementLoading: true, engagementRange: resolved });
    try {
      const response = await fetch(
        apiUrl(
          `/guilds/${guildId}/analytics/engagement?range=${resolved}`
        ),
        { method: "GET", cache: "no-store" }
      );
      if (!response.ok) {
        set({ engagement: null, engagementLoading: false });
        return;
      }
      const data = (await response.json()) as EngagementResponse;
      set({ engagement: data, engagementLoading: false });
    } catch {
      set({ engagement: null, engagementLoading: false });
    }
  },
}));
