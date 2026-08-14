"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";

export type AuthUser = {
  user_id: string;
  username: string;
  global_name: string | null;
  avatar: string | null;
  expires_at: number;
};

type AuthState = {
  user: AuthUser | null;
  authenticated: boolean;
  loading: boolean;
  reload: () => Promise<void>;
  logout: () => Promise<void>;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  authenticated: false,
  loading: true,
  reload: async () => {
    set({ loading: true });
    try {
      const response = await fetch(apiUrl("/api/v1/sessions/me"), {
        cache: "no-store",
        credentials: "include",
      });
      if (!response.ok) {
        set({ user: null, authenticated: false, loading: false });
        return;
      }
      const data = (await response.json()) as {
        authenticated: boolean;
        user: AuthUser | null;
      };
      set({
        authenticated: Boolean(data.authenticated),
        user: data.user,
        loading: false,
      });
    } catch {
      set({ user: null, authenticated: false, loading: false });
    }
  },
  logout: async () => {
    try {
      await fetch(apiUrl("/api/v1/sessions/logout"), {
        method: "POST",
        credentials: "include",
      });
    } finally {
      set({ user: null, authenticated: false, loading: false });
    }
  },
}));
