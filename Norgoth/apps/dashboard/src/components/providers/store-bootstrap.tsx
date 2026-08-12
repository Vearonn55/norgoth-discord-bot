"use client";

import { useEffect } from "react";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { usePrefsStore } from "@/stores/prefs-store";
import { useGuildStore } from "@/stores/guild-store";
import { useUiStore } from "@/stores/ui-store";

function isServerSelectorPath(pathname: string | null): boolean {
  if (!pathname) return false;
  return /\/servers\/?$/.test(pathname);
}

export function StoreBootstrap({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const hydratePrefs = usePrefsStore((s) => s.hydrate);
  const hydrateNavScroll = useUiStore((s) => s.hydrateNavScroll);
  const reloadGuild = useGuildStore((s) => s.reload);

  useEffect(() => {
    hydratePrefs();
    hydrateNavScroll();

    // After Discord OAuth the server selector already fetches
    // GET /sessions/servers. Reloading guild resources here races a second
    // (and often third) Discord GET /users/@me/guilds and triggers 429.
    // Read pathname only on layout mount — AppShell persists across child
    // navigations, and selectGuild handles the post-pick load.
    if (isServerSelectorPath(pathname)) {
      useGuildStore.setState({ loading: false, error: null });
      return;
    }

    void reloadGuild();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one-shot layout bootstrap
  }, [hydratePrefs, hydrateNavScroll, reloadGuild]);

  return children;
}
