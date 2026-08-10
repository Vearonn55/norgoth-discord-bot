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
import { cilPeople, cilSearch } from "@coreui/icons";
import { locales, type Locale } from "@/i18n/config";
import type { Dictionary } from "@/app/[lang]/dictionaries";
import { usePreferencesContext } from "@/components/providers/preferences-provider";
import { useUiStore } from "@/stores/ui-store";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useAuthStore } from "@/stores/auth-store";
import { apiUrl } from "@/lib/api";
import { formatNumber } from "@/lib/number";

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

  const { selectedGuild, resources } = useFirstGuild();
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

  const connected = Boolean(health?.connected);
  // Member count comes from the already-loaded guild resources (a cheap Redis
  // read via the shared guild store), keeping a single source of truth and
  // avoiding extra Discord API calls.
  const memberCount = resources?.member_count ?? null;
  const memberCountLabel = lang === "tr" ? "Üye Sayısı" : "Member Count";
  const searchPlaceholder =
    dict.common.searchPlaceholder ||
    (lang === "tr" ? "Özellik ara…" : "Search features…");

  return (
    <CHeader
      position={preferences.stickyTopbar ? "sticky" : undefined}
      className="norgoth-topbar mb-0 px-4"
    >
      <CHeaderNav className="norgoth-topbar-nav d-flex align-items-center gap-3 w-100">
        <div className="norgoth-topbar-left d-flex align-items-center gap-3">
          <CBadge
            color={connected ? "success" : "danger"}
            shape="rounded-pill"
            className="px-3 py-2"
          >
            {connected ? "Online" : "Offline"}
          </CBadge>
          {selectedGuild && memberCount !== null ? (
            <CHeaderText className="d-none d-md-flex align-items-center gap-2 mb-0 text-white">
              <CIcon icon={cilPeople} className="text-body-secondary" />
              <span className="small text-body-secondary">
                {memberCountLabel}:
              </span>
              <span className="fw-semibold">
                {formatNumber(memberCount, lang)}
              </span>
            </CHeaderText>
          ) : null}
        </div>

        <div className="norgoth-topbar-center flex-grow-1 d-flex justify-content-center">
          <button
            type="button"
            className="norgoth-topbar-search"
            onClick={() => setCommandPaletteOpen(true)}
            aria-label={searchPlaceholder}
          >
            <CIcon icon={cilSearch} className="text-body-secondary flex-shrink-0" />
            <span className="norgoth-topbar-search-label text-body-secondary text-truncate">
              {searchPlaceholder}
            </span>
            <kbd className="norgoth-topbar-search-kbd small text-body-secondary d-none d-lg-inline">
              ⌘K
            </kbd>
          </button>
          <CButton
            color="secondary"
            variant="outline"
            size="sm"
            className="norgoth-topbar-search-compact d-flex d-md-none align-items-center"
            onClick={() => setCommandPaletteOpen(true)}
            aria-label={searchPlaceholder}
          >
            <CIcon icon={cilSearch} />
          </CButton>
        </div>

        <div className="norgoth-topbar-right d-flex align-items-center gap-2">
          {authUser ? (
            <span className="small text-body-secondary d-none d-xl-inline">
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
