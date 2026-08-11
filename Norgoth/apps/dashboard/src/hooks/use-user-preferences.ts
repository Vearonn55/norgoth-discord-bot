"use client";

import { useEffect, useState } from "react";
import {
  DEFAULT_PREFERENCES,
  getUserPreferences,
  saveUserPreferences,
  type UserPreferences,
} from "@/lib/preferences-storage";

export function useUserPreferences() {
  const [preferences, setPreferences] =
    useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const stored = getUserPreferences();
    setPreferences(stored);
    setIsReady(true);
  }, []);

  function updatePreferences(next: UserPreferences) {
    setPreferences(next);
    saveUserPreferences(next);
  }

  function patchPreferences(patch: Partial<UserPreferences>) {
    setPreferences((prev) => {
      const next = {
        ...prev,
        ...patch,
      };

      saveUserPreferences(next);
      return next;
    });
  }

  return {
    preferences,
    setPreferences: updatePreferences,
    patchPreferences,
    isReady,
  };
}
