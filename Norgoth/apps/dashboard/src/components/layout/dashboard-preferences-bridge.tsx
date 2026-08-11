"use client";

import { useEffect } from "react";
import { usePrefsStore } from "@/stores/prefs-store";

export default function DashboardPreferencesBridge() {
  const preferences = usePrefsStore((s) => s.preferences);
  const isReady = usePrefsStore((s) => s.isReady);

  useEffect(() => {
    if (!isReady) return;

    const root = document.documentElement;
    root.dataset.compactSidebar = preferences.compactSidebar ? "true" : "false";
    root.dataset.denseTables = preferences.denseTables ? "true" : "false";
    root.dataset.reducedMotion = preferences.reducedMotion ? "true" : "false";
    root.dataset.stickyTopbar = preferences.stickyTopbar ? "true" : "false";

    if (preferences.reducedMotion) {
      root.style.scrollBehavior = "auto";
    } else {
      root.style.removeProperty("scroll-behavior");
    }
  }, [preferences, isReady]);

  return null;
}
