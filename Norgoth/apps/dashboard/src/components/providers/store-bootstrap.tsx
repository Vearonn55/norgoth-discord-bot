"use client";

import { useEffect } from "react";
import type { ReactNode } from "react";
import { usePrefsStore } from "@/stores/prefs-store";
import { useGuildStore } from "@/stores/guild-store";
import { useUiStore } from "@/stores/ui-store";

export function StoreBootstrap({ children }: { children: ReactNode }) {
  const hydratePrefs = usePrefsStore((s) => s.hydrate);
  const hydrateNavScroll = useUiStore((s) => s.hydrateNavScroll);
  const reloadGuild = useGuildStore((s) => s.reload);

  useEffect(() => {
    hydratePrefs();
    hydrateNavScroll();
    void reloadGuild();
  }, [hydratePrefs, hydrateNavScroll, reloadGuild]);

  return children;
}
