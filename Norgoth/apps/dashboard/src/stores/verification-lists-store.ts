"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";

export type HighRiskGuildEntry = {
  id: string;
  guild_id: string;
  high_risk_discord_guild_id: string;
  reason: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type WhitelistEntry = {
  id: string;
  guild_id: string;
  discord_user_id: string;
  list_type: string;
  reason: string | null;
  created_at: string;
  updated_at: string;
};

type MutationResult = { ok: boolean; error?: string };

type VerificationListsState = {
  highRisk: HighRiskGuildEntry[];
  highRiskLoading: boolean;
  highRiskError: string | null;
  whitelist: WhitelistEntry[];
  whitelistLoading: boolean;
  whitelistError: string | null;
  loadHighRisk: (guildId: string) => Promise<void>;
  addHighRisk: (
    guildId: string,
    targetGuildId: string,
    reason: string
  ) => Promise<MutationResult>;
  removeHighRisk: (
    guildId: string,
    targetGuildId: string
  ) => Promise<MutationResult>;
  loadWhitelist: (guildId: string) => Promise<void>;
  addWhitelist: (
    guildId: string,
    userId: string,
    reason: string
  ) => Promise<MutationResult>;
  removeWhitelist: (guildId: string, userId: string) => Promise<MutationResult>;
};

async function safeError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return String(body?.detail ?? body?.error?.message ?? `HTTP ${response.status}`);
  } catch {
    return `HTTP ${response.status}`;
  }
}

export const useVerificationListsStore = create<VerificationListsState>((set, get) => ({
  highRisk: [],
  highRiskLoading: false,
  highRiskError: null,
  whitelist: [],
  whitelistLoading: false,
  whitelistError: null,

  loadHighRisk: async (guildId) => {
    set({ highRiskLoading: true, highRiskError: null });
    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/high-risk-guilds`),
        { cache: "no-store" }
      );
      if (!response.ok) {
        set({ highRiskError: await safeError(response) });
        return;
      }
      set({ highRisk: (await response.json()) as HighRiskGuildEntry[] });
    } catch {
      set({ highRiskError: "Could not reach the Norgoth API." });
    } finally {
      set({ highRiskLoading: false });
    }
  },

  addHighRisk: async (guildId, targetGuildId, reason) => {
    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/high-risk-guilds/${targetGuildId}`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: reason || null }),
        }
      );
      if (!response.ok) return { ok: false, error: await safeError(response) };
      await get().loadHighRisk(guildId);
      return { ok: true };
    } catch {
      return { ok: false, error: "Could not reach the Norgoth API." };
    }
  },

  removeHighRisk: async (guildId, targetGuildId) => {
    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/high-risk-guilds/${targetGuildId}`),
        { method: "DELETE" }
      );
      if (!response.ok && response.status !== 204) {
        return { ok: false, error: await safeError(response) };
      }
      await get().loadHighRisk(guildId);
      return { ok: true };
    } catch {
      return { ok: false, error: "Could not reach the Norgoth API." };
    }
  },

  loadWhitelist: async (guildId) => {
    set({ whitelistLoading: true, whitelistError: null });
    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/user-list?list_type=whitelist`),
        { cache: "no-store" }
      );
      if (!response.ok) {
        set({ whitelistError: await safeError(response) });
        return;
      }
      set({ whitelist: (await response.json()) as WhitelistEntry[] });
    } catch {
      set({ whitelistError: "Could not reach the Norgoth API." });
    } finally {
      set({ whitelistLoading: false });
    }
  },

  addWhitelist: async (guildId, userId, reason) => {
    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/user-list/${userId}`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ list_type: "whitelist", reason: reason || null }),
        }
      );
      if (!response.ok) return { ok: false, error: await safeError(response) };
      await get().loadWhitelist(guildId);
      return { ok: true };
    } catch {
      return { ok: false, error: "Could not reach the Norgoth API." };
    }
  },

  removeWhitelist: async (guildId, userId) => {
    try {
      const response = await fetch(
        apiUrl(`/api/v1/guilds/${guildId}/user-list/${userId}`),
        { method: "DELETE" }
      );
      if (!response.ok && response.status !== 204) {
        return { ok: false, error: await safeError(response) };
      }
      await get().loadWhitelist(guildId);
      return { ok: true };
    } catch {
      return { ok: false, error: "Could not reach the Norgoth API." };
    }
  },
}));
