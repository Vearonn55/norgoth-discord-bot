"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";

export type ModuleFlag = {
  key: string;
  name: string;
  description: string;
  enabled: boolean;
};

type ModulesState = {
  modules: ModuleFlag[];
  loading: boolean;
  error: string | null;
  pendingKey: string | null;
  load: (guildId: string) => Promise<void>;
  toggleModule: (
    guildId: string,
    key: string,
    enabled: boolean
  ) => Promise<void>;
};

export const useModulesStore = create<ModulesState>((set, get) => ({
  modules: [],
  loading: true,
  error: null,
  pendingKey: null,
  load: async (guildId) => {
    set({ loading: true, error: null });

    try {
      const response = await fetch(apiUrl(`/guilds/${guildId}/modules`), {
        cache: "no-store",
      });

      if (!response.ok) {
        set({ error: "Could not load module switches from the API." });
        return;
      }

      const payload = await response.json();

      if (Array.isArray(payload.modules)) {
        set({ modules: payload.modules as ModuleFlag[] });
      }
    } catch {
      set({ error: "Could not reach the Norgoth API." });
    } finally {
      set({ loading: false });
    }
  },
  toggleModule: async (guildId, key, enabled) => {
    set({
      pendingKey: key,
      modules: get().modules.map((module) =>
        module.key === key ? { ...module, enabled } : module
      ),
      error: null,
    });

    try {
      const response = await fetch(apiUrl(`/guilds/${guildId}/modules`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ modules: { [key]: enabled } }),
      });

      if (!response.ok) {
        throw new Error("save failed");
      }

      const payload = await response.json();

      if (Array.isArray(payload.modules)) {
        set({ modules: payload.modules as ModuleFlag[] });
      }
    } catch {
      set({
        modules: get().modules.map((module) =>
          module.key === key ? { ...module, enabled: !enabled } : module
        ),
        error: "Saving the module switch failed. Try again.",
      });
    } finally {
      set({ pendingKey: null });
    }
  },
}));
