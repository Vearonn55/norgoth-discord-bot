"use client";

import { create } from "zustand";
import {
  defaultDateRange,
  type DateRangeValue,
} from "@/components/ui/date-range-filter";
import { apiUrl } from "@/lib/api";
import {
  defaultCampaignWizardState,
  type CampaignWizardState,
} from "@/types/campaign";

export type CampaignStatus =
  | "draft"
  | "scheduled"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "stopped";

export type Campaign = {
  id: string;
  title?: string;
  name?: string;
  message?: string;
  status: CampaignStatus | string;
  audience_count?: number;
  sent_count?: number;
  failed_count?: number;
  retry_count?: number;
  permanent_failed_count?: number;
  platform_results?: Record<
    string,
    {
      sent_count?: number;
      failed_count?: number;
      retry_count?: number;
      permanent_failed_count?: number;
    }
  >;
  executed_at?: string | null;
  created_at?: string;
  updated_at?: string;
};

function normalizeCampaignItems(data: unknown): Campaign[] {
  if (Array.isArray(data)) return data as Campaign[];

  if (
    data &&
    typeof data === "object" &&
    "items" in data &&
    Array.isArray((data as { items?: unknown }).items)
  ) {
    return (data as { items: Campaign[] }).items;
  }

  if (
    data &&
    typeof data === "object" &&
    "campaigns" in data &&
    Array.isArray((data as { campaigns?: unknown }).campaigns)
  ) {
    return (data as { campaigns: Campaign[] }).campaigns;
  }

  return [];
}

type CampaignsState = {
  campaigns: Campaign[];
  loading: boolean;
  query: string;
  statusFilter: string;
  dateRange: DateRangeValue;
  wizardStep: number;
  wizardState: CampaignWizardState;
  setQuery: (query: string) => void;
  setStatusFilter: (status: string) => void;
  setDateRange: (range: DateRangeValue) => void;
  setWizardStep: (step: number | ((prev: number) => number)) => void;
  setWizardState: (
    state:
      | CampaignWizardState
      | ((prev: CampaignWizardState) => CampaignWizardState)
  ) => void;
  resetWizard: (initial?: CampaignWizardState) => void;
  loadCampaigns: () => Promise<void>;
  deleteCampaign: (id: string) => Promise<boolean>;
};

export const useCampaignsStore = create<CampaignsState>((set) => ({
  campaigns: [],
  loading: true,
  query: "",
  statusFilter: "all",
  dateRange: defaultDateRange(30),
  wizardStep: 1,
  wizardState: defaultCampaignWizardState,
  setQuery: (query) => set({ query }),
  setStatusFilter: (statusFilter) => set({ statusFilter }),
  setDateRange: (dateRange) => set({ dateRange }),
  setWizardStep: (step) =>
    set((state) => ({
      wizardStep: typeof step === "function" ? step(state.wizardStep) : step,
    })),
  setWizardState: (wizardState) =>
    set((state) => ({
      wizardState:
        typeof wizardState === "function"
          ? wizardState(state.wizardState)
          : wizardState,
    })),
  resetWizard: (initial) =>
    set({
      wizardStep: 1,
      wizardState: initial ?? defaultCampaignWizardState,
    }),
  loadCampaigns: async () => {
    try {
      const response = await fetch(apiUrl(`/campaigns`), {
        cache: "no-store",
      });

      if (!response.ok) {
        set({ campaigns: [], loading: false });
        return;
      }

      const data = await response.json();
      set({ campaigns: normalizeCampaignItems(data), loading: false });
    } catch {
      set({ campaigns: [], loading: false });
    }
  },
  deleteCampaign: async (id) => {
    try {
      const response = await fetch(apiUrl(`/campaigns/${id}`), {
        method: "DELETE",
      });
      if (!response.ok) return false;
      set((state) => ({
        campaigns: state.campaigns.filter((campaign) => campaign.id !== id),
      }));
      return true;
    } catch {
      return false;
    }
  },
}));

export function campaignDateStamp(campaign: Campaign): string | null {
  return (
    campaign.updated_at ||
    campaign.executed_at ||
    campaign.created_at ||
    null
  );
}
