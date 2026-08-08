"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  CBadge,
  CButton,
  CFormSelect,
  CHeader,
  CHeaderNav,
  CHeaderText,
} from "@coreui/react";
import { CIcon } from "@coreui/icons-react";
import { cilSearch } from "@coreui/icons";
import { locales, type Locale } from "@/i18n/config";
import type { Dictionary } from "@/app/[lang]/dictionaries";
import { usePreferencesContext } from "@/components/providers/preferences-provider";
import { useUiStore } from "@/stores/ui-store";
import { GuildSwitcher } from "@/components/layout/guild-switcher";
import { useGuildStore } from "@/stores/guild-store";
import { useAuthStore } from "@/stores/auth-store";
import { apiUrl } from "@/lib/api";

type TopbarProps = {
  lang: Locale;
  dict: Dictionary;
};

type BotHealth = {
  connected: boolean;
  status?: {
    guilds?: Array<{ id: string; name: string; member_count?: number }>;
  };
};

function replaceLocaleInPathname(pathname: string, nextLocale: Locale) {
  const parts = pathname.split("/").filter(Boolean);

  if (parts.length === 0) return `/${nextLocale}`;

  if (locales.includes(parts[0] as Locale)) {
    parts[0] = nextLocale;
    return `/${parts.join("/")}`;
  }

  return `/${nextLocale}/${parts.join("/")}`;
}

export function Topbar({ lang, dict }: TopbarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { preferences } = usePreferencesContext();
  const setCommandPaletteOpen = useUiStore((s) => s.setCommandPaletteOpen);

  const selectedGuild = useGuildStore((s) => s.selectedGuild);
  const authUser = useAuthStore((s) => s.user);
  const reloadAuth = useAuthStore((s) => s.reload);
  const logout = useAuthStore((s) => s.logout);

  useEffect(() => {
    void reloadAuth();
  }, [reloadAuth]);

  const [health, setHealth] = useState<BotHealth | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadHealth() {
      try {
        const response = await fetch(apiUrl(`/bot/health`), {
          cache: "no-store",
        });

        if (!response.ok) return;

        const data = (await response.json()) as BotHealth;

        if (!cancelled) setHealth(data);
      } catch {
        if (!cancelled) setHealth(null);
      }
    }

    void loadHealth();

    const interval = window.setInterval(loadHealth, 15000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  function handleLanguageChange(nextLocale: Locale) {
    router.push(replaceLocaleInPathname(pathname, nextLocale));
  }

  const guild = selectedGuild
    ? { name: selectedGuild.name, member_count: health?.status?.guilds?.find((g) => g.id === selectedGuild.id)?.member_count }
    : health?.status?.guilds?.[0];
  const connected = Boolean(health?.connected);

  return (
    <CHeader
      position={preferences.stickyTopbar ? "sticky" : undefined}
      className="norgoth-topbar mb-0 px-4"
    >
      <CHeaderNav className="d-flex flex-grow-1 align-items-center justify-content-between gap-3 w-100">
        <div className="d-flex align-items-center gap-3">
          <CBadge
            color={connected ? "success" : "danger"}
            shape="rounded-pill"
            className="px-3 py-2"
          >
            {connected ? "Online" : "Offline"}
          </CBadge>
          <GuildSwitcher />
          <div className="d-flex flex-column d-none d-md-flex">
            <CHeaderText className="fw-semibold text-white mb-0">
              {guild
                ? guild.name
                : connected
                  ? "Connected"
                  : "Bot offline"}
            </CHeaderText>
            {guild?.member_count ? (
              <span className="small text-body-secondary">
                {guild.member_count.toLocaleString()} members
              </span>
            ) : null}
          </div>
        </div>

        <div className="d-flex align-items-center gap-2">
          {authUser ? (
            <span className="small text-body-secondary d-none d-lg-inline">
              {authUser.global_name || authUser.username}
            </span>
          ) : null}
          {authUser ? (
            <CButton
              color="secondary"
              variant="outline"
              size="sm"
              onClick={() => {
                void logout().then(() => router.push(`/${lang}`));
              }}
            >
              Log out
            </CButton>
          ) : null}
          <CButton
            color="secondary"
            variant="outline"
            size="sm"
            className="d-flex align-items-center gap-2"
            onClick={() => setCommandPaletteOpen(true)}
            aria-label="Open command palette"
          >
            <CIcon icon={cilSearch} />
            <span className="d-none d-md-inline">Search</span>
            <kbd className="small d-none d-lg-inline text-body-secondary">
              ⌘K
            </kbd>
          </CButton>
          <CFormSelect
            value={lang}
            onChange={(e) => handleLanguageChange(e.target.value as Locale)}
            aria-label={dict.common.language}
            style={{ width: "auto", minWidth: 88 }}
            size="sm"
          >
            <option value="en">EN</option>
            <option value="tr">TR</option>
          </CFormSelect>
        </div>
      </CHeaderNav>
    </CHeader>
  );
}
