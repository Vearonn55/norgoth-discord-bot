"use client";

import { create } from "zustand";
import {
  DEFAULT_PREFERENCES,
  getUserPreferences,
  saveUserPreferences,
  type UserPreferences,
} from "@/lib/preferences-storage";

type PrefsState = {
  preferences: UserPreferences;
  isReady: boolean;
  hydrate: () => void;
  setPreferences: (next: UserPreferences) => void;
  patchPreferences: (patch: Partial<UserPreferences>) => void;
};

export const usePrefsStore = create<PrefsState>((set, get) => ({
  preferences: DEFAULT_PREFERENCES,
  isReady: false,
  hydrate: () => {
    set({ preferences: getUserPreferences(), isReady: true });
  },
  setPreferences: (next) => {
    saveUserPreferences(next);
    set({ preferences: next });
  },
  patchPreferences: (patch) => {
    const next = { ...get().preferences, ...patch };
    saveUserPreferences(next);
    set({ preferences: next });
  },
}));
