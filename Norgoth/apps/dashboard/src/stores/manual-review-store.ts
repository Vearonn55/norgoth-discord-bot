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

export type MatchedBannedAccount = {
  discord_user_id: string;
  display_name: string | null;
  username: string | null;
  source: string;
  resolved_at: string | null;
};

/** Read-only transcript detail for one attempt. */
export type ManualReviewDetail = ManualReviewItem & {
  matched_high_risk_servers: MatchedHighRiskServer[];
  matched_banned_accounts?: MatchedBannedAccount[];
  review_reasons?: string[];
  proxy_classification?: string | null;
};

export type ManualReviewStatusFilter =
  | "manual_review"
  | "success"
  | "failed"
  | "all";

export type ManualReviewErrorKey =
  | "queueLoadError"
  | "queueForbidden"
  | "queueNotFound"
  | "queueReachError"
  | "detailNotFound"
  | "detailForbidden"
  | "detailLoadError"
  | "detailReachError";

type ListResponse = {
  items: ManualReviewItem[];
  total: number;
};

const PAGE_SIZE = 10;

const FETCH_OPTS: RequestInit = {
  cache: "no-store",
  credentials: "include",
};

export function manualReviewListErrorKey(status: number): ManualReviewErrorKey {
  if (status === 404) return "queueNotFound";
  if (status === 403) return "queueForbidden";
  return "queueLoadError";
}

export function manualReviewDetailErrorKey(status: number): ManualReviewErrorKey {
  if (status === 404) return "detailNotFound";
  if (status === 403) return "detailForbidden";
  return "detailLoadError";
}

type ManualReviewState = {
  items: ManualReviewItem[];
  total: number;
  page: number;
  pageSize: number;
  query: string;
  statusFilter: ManualReviewStatusFilter;
  loading: boolean;
  errorKey: ManualReviewErrorKey | null;

  detail: ManualReviewDetail | null;
  detailLoading: boolean;
  detailErrorKey: ManualReviewErrorKey | null;

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
  errorKey: null,

  detail: null,
  detailLoading: true,
  detailErrorKey: null,

  reviewingId: null,
  reviewError: null,

  setPage: (page) => set({ page: Math.max(1, page) }),
  setQuery: (query) => set({ query, page: 1 }),
  setStatusFilter: (statusFilter) => set({ statusFilter, page: 1 }),

  load: async (guildId) => {
    const { page, pageSize, query, statusFilter } = get();
    set({ loading: true, errorKey: null });

    const params = new URLSearchParams({
      limit: String(pageSize),
      offset: String((page - 1) * pageSize),
    });
    if (query.trim()) params.set("q", query.trim());
    if (statusFilter !== "all") params.set("status", statusFilter);

    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/verification-logs?${params.toString()}`),
        FETCH_OPTS
      );

      if (!response.ok) {
        set({
          errorKey: manualReviewListErrorKey(response.status),
          items: [],
          total: 0,
        });
        return;
      }

      const data = (await response.json()) as ListResponse;
      set({ items: data.items, total: data.total, errorKey: null });
    } catch {
      set({
        errorKey: "queueReachError",
        items: [],
        total: 0,
      });
    } finally {
      set({ loading: false });
    }
  },

  loadDetail: async (guildId, attemptId) => {
    set({ detailLoading: true, detailErrorKey: null, detail: null });

    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/verification-logs/${attemptId}`),
        FETCH_OPTS
      );

      if (!response.ok) {
        set({
          detailErrorKey: manualReviewDetailErrorKey(response.status),
        });
        return;
      }

      set({ detail: (await response.json()) as ManualReviewDetail });
    } catch {
      set({ detailErrorKey: "detailReachError" });
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
          ...FETCH_OPTS,
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
      const error = "queueReachError";
      set({ reviewError: error });
      return { ok: false, error };
    } finally {
      set({ reviewingId: null });
    }
  },
}));
