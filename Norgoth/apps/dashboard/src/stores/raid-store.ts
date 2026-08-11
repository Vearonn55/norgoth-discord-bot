"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";

export type RaidConfig = {
  enabled: boolean;
  alert_channel_id: string | null;
  joins_per_minute: number;
  young_account_age_days: number;
  young_account_ratio: number;
  response_duration_minutes: number;
  respond_automatically: boolean;
  pause_invites: boolean;
  force_verification: boolean;
  kick_young_accounts: boolean;
  pause_invite_crediting: boolean;
  active_incident?: Record<string, unknown> | null;
};

type RaidState = {
  config: RaidConfig | null;
  incidents: Record<string, unknown>[];
  incidentsTotal: number;
  loading: boolean;
  saving: boolean;
  error: string | null;
  load: (guildId: string) => Promise<void>;
  save: (guildId: string, config: RaidConfig) => Promise<void>;
  loadIncidents: (guildId: string, offset?: number) => Promise<void>;
};

const defaults: RaidConfig = {
  enabled: false,
  alert_channel_id: null,
  joins_per_minute: 10,
  young_account_age_days: 7,
  young_account_ratio: 50,
  response_duration_minutes: 30,
  respond_automatically: false,
  pause_invites: false,
  force_verification: false,
  kick_young_accounts: false,
  pause_invite_crediting: false,
};

export const useRaidStore = create<RaidState>((set) => ({
  config: null,
  incidents: [],
  incidentsTotal: 0,
  loading: false,
  saving: false,
  error: null,
  load: async (guildId) => {
    set({ loading: true, error: null });
    try {
      const response = await fetch(apiUrl(`/guilds/${guildId}/raid`), {
        cache: "no-store",
        credentials: "include",
      });
      if (!response.ok) throw new Error("Failed to load raid config");
      const data = await response.json();
      set({
        config: { ...defaults, ...data },
        loading: false,
      });
    } catch (e) {
      set({
        loading: false,
        error: e instanceof Error ? e.message : "Load failed",
      });
    }
  },
  save: async (guildId, config) => {
    set({ saving: true, error: null });
    try {
      const { active_incident: _, ...body } = config;
      const response = await fetch(apiUrl(`/guilds/${guildId}/raid`), {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...body,
          alert_channel_id: body.alert_channel_id || null,
        }),
      });
      if (!response.ok) throw new Error("Failed to save raid config");
      const data = await response.json();
      set({ config: { ...defaults, ...data }, saving: false });
    } catch (e) {
      set({
        saving: false,
        error: e instanceof Error ? e.message : "Save failed",
      });
    }
  },
  loadIncidents: async (guildId, offset = 0) => {
    const response = await fetch(
      apiUrl(`/guilds/${guildId}/raid/incidents?offset=${offset}&limit=50`),
      { cache: "no-store", credentials: "include" }
    );
    if (!response.ok) return;
    const data = await response.json();
    set({
      incidents: data.items ?? [],
      incidentsTotal: data.total ?? 0,
    });
  },
}));
