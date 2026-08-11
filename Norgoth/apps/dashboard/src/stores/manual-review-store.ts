"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";
import type { VerificationLog } from "@/stores/verification-store";

/** A single reviewable verification attempt (queue row). */
export type ManualReviewItem = VerificationLog;

export type MatchedHighRiskServer = {
  discord_guild_id: string;
  reason: string | null;
};

/** Read-only transcript detail for one attempt. */
export type ManualReviewDetail = ManualReviewItem & {
  matched_high_risk_servers: MatchedHighRiskServer[];
};

export type ManualReviewStatusFilter =
  | "manual_review"
  | "success"
  | "failed"
  | "all";

type ListResponse = {
  items: ManualReviewItem[];
  total: number;
};

const PAGE_SIZE = 10;

type ManualReviewState = {
  items: ManualReviewItem[];
  total: number;
  page: number;
  pageSize: number;
  query: string;
  statusFilter: ManualReviewStatusFilter;
  loading: boolean;
  error: string | null;

  detail: ManualReviewDetail | null;
  detailLoading: boolean;
  detailError: string | null;

  reviewingId: string | null;
  reviewError: string | null;

  setPage: (page: number) => void;
  setQuery: (query: string) => void;
  setStatusFilter: (status: ManualReviewStatusFilter) => void;
  load: (guildId: string) => Promise<void>;
  loadDetail: (guildId: string, attemptId: string) => Promise<void>;
  review: (
    guildId: string,
    attemptId: string,
    approved: boolean
  ) => Promise<{ ok: boolean; error?: string }>;
};

export const useManualReviewStore = create<ManualReviewState>((set, get) => ({
  items: [],
  total: 0,
  page: 1,
  pageSize: PAGE_SIZE,
  query: "",
  statusFilter: "manual_review",
  loading: true,
  error: null,

  detail: null,
  detailLoading: true,
  detailError: null,

  reviewingId: null,
  reviewError: null,

  setPage: (page) => set({ page: Math.max(1, page) }),
  setQuery: (query) => set({ query, page: 1 }),
  setStatusFilter: (statusFilter) => set({ statusFilter, page: 1 }),

  load: async (guildId) => {
    const { page, pageSize, query, statusFilter } = get();
    set({ loading: true, error: null });

    const params = new URLSearchParams({
      limit: String(pageSize),
      offset: String((page - 1) * pageSize),
    });
    if (query.trim()) params.set("q", query.trim());
    if (statusFilter !== "all") params.set("status", statusFilter);

    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/verification-logs?${params.toString()}`),
        { cache: "no-store" }
      );

      if (!response.ok) {
        set({
          error:
            response.status === 404
              ? "Guild is not registered in the verification domain yet."
              : response.status === 403
                ? "You do not have permission to review this server."
                : "Could not load the manual verification queue.",
        });
        return;
      }

      const data = (await response.json()) as ListResponse;
      set({ items: data.items, total: data.total });
    } catch {
      set({ error: "Could not reach the Norgoth API." });
    } finally {
      set({ loading: false });
    }
  },

  loadDetail: async (guildId, attemptId) => {
    set({ detailLoading: true, detailError: null, detail: null });

    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/verification-logs/${attemptId}`),
        { cache: "no-store" }
      );

      if (!response.ok) {
        set({
          detailError:
            response.status === 404
              ? "This review record could not be found."
              : response.status === 403
                ? "You do not have permission to view this record."
                : "Could not load the review record.",
        });
        return;
      }

      set({ detail: (await response.json()) as ManualReviewDetail });
    } catch {
      set({ detailError: "Could not reach the Norgoth API." });
    } finally {
      set({ detailLoading: false });
    }
  },

  review: async (guildId, attemptId, approved) => {
    set({ reviewingId: attemptId, reviewError: null });

    try {
      const response = await fetch(
        apiUrl(
          `/api/v1/guilds/${guildId}/verification-logs/${attemptId}/review`
        ),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ approved }),
        }
      );

      if (!response.ok) {
        let detail = `HTTP ${response.status}`;
        try {
          const body = await response.json();
          detail = String(body?.detail ?? detail);
        } catch {
          /* ignore */
        }
        set({ reviewError: detail });
        return { ok: false, error: detail };
      }

      const updated = (await response.json()) as ManualReviewItem;
      set((state) => ({
        items: state.items.map((item) =>
          item.id === updated.id ? updated : item
        ),
      }));
      return { ok: true };
    } catch {
      const error = "Could not reach the Norgoth API.";
      set({ reviewError: error });
      return { ok: false, error };
    } finally {
      set({ reviewingId: null });
    }
  },
}));
