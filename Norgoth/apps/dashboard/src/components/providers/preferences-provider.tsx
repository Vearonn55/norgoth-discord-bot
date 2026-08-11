"use client";

import { usePrefsStore } from "@/stores/prefs-store";

/** Compatibility shim for former PreferencesContext consumers. */
export function usePreferencesContext() {
  const preferences = usePrefsStore((s) => s.preferences);
  const patchPreferences = usePrefsStore((s) => s.patchPreferences);
  const isReady = usePrefsStore((s) => s.isReady);
  return { preferences, patchPreferences, isReady };
}

export function PreferencesProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
