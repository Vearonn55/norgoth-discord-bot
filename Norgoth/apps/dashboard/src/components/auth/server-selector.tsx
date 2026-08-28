"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  CButton,
  CContainer,
  CPagination,
  CPaginationItem,
} from "@coreui/react";
import { apiUrl, browserApiUrl } from "@/lib/api";
import {
  isReconnectErrorCode,
  isRetryErrorCode,
  readApiError,
} from "@/lib/api-error";
import { resolveSetupState } from "@/lib/server-setup-state";
import { useGuildStore, type SelectedGuild } from "@/stores/guild-store";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import {
  ServerGuildCard,
  type ServerGuildItem,
} from "@/components/auth/server-guild-card";

const PAGE_SIZE = 12;
const INSTALL_POLL_MS = 5000;
const INSTALL_POLL_MAX_MS = 120_000;

type ServersCopy = {
  title: string;
  subtitle: string;
  loading: string;
  empty: string;
  available: string;
  installed: string;
  notInstalled: string;
  manage: string;
  install: string;
  installAria: string;
  addNorgoth: string;
  refresh: string;
  roleOwner: string;
  roleAdministrator: string;
  roleManageServer: string;
  retry: string;
  reconnect: string;
  errorGeneric: string;
  errorAuth: string;
  errorScope: string;
  errorRateLimited: string;
  errorUnavailable: string;
  requestId: string;
  awaitingInstall: string;
  installTimedOut: string;
  pageOf: string;
  previousPage: string;
  nextPage: string;
};

const FALLBACK_COPY: Record<"en" | "tr", ServersCopy> = {
  en: {
    title: "Your Servers",
    subtitle:
      "Choose a Discord server to manage. Only servers where you have Manage Server or Administrator permission are listed.",
    loading: "Loading servers…",
    empty:
      "No manageable servers found. Make sure you have Manage Server permission, then install NorBot from a server card.",
    available: "Available to manage",
    installed: "Installed",
    notInstalled: "Not Installed",
    manage: "Manage",
    install: "Install",
    installAria: "Install NorBot on {name}",
    addNorgoth: "Install",
    refresh: "Refresh",
    roleOwner: "Owner",
    roleAdministrator: "Administrator",
    roleManageServer: "Manage Server",
    retry: "Retry",
    reconnect: "Reconnect Discord",
    errorGeneric: "Could not load your Discord servers.",
    errorAuth:
      "Your Discord authorization expired or is missing required permissions. Reconnect Discord to continue.",
    errorScope:
      "Discord access is missing the guilds permission. Reconnect Discord and approve all requested scopes.",
    errorRateLimited:
      "Discord is rate-limiting requests. Please wait a moment and retry.",
    errorUnavailable: "Discord is temporarily unavailable. Please retry.",
    requestId: "Support reference: {id}",
    awaitingInstall: "Waiting for NorBot to join {name}…",
    installTimedOut:
      "Still waiting for install on {name}. Refresh or open Install again if you finished in Discord.",
    pageOf: "Page {page} of {pages}",
    previousPage: "Previous",
    nextPage: "Next",
  },
  tr: {
    title: "Sunucularınız",
    subtitle:
      "Yönetmek istediğiniz Discord sunucusunu seçin. Yalnızca Sunucuyu Yönet veya Yönetici izniniz olan sunucular listelenir.",
    loading: "Sunucular yükleniyor…",
    empty:
      "Yönetilebilir sunucu bulunamadı. Sunucuyu Yönet izniniz olduğundan emin olun, ardından bir sunucu kartından NorBot’u yükleyin.",
    available: "Yönetime hazır",
    installed: "Yüklü",
    notInstalled: "Yüklü Değil",
    manage: "Yönet",
    install: "Yükle",
    installAria: "NorBot’u {name} sunucusuna yükle",
    addNorgoth: "Yükle",
    refresh: "Yenile",
    roleOwner: "Sahip",
    roleAdministrator: "Yönetici",
    roleManageServer: "Sunucuyu Yönet",
    retry: "Yeniden dene",
    reconnect: "Discord’u yeniden bağla",
    errorGeneric: "Discord sunucularınız yüklenemedi.",
    errorAuth:
      "Discord yetkinizin süresi dolmuş veya gerekli izinler eksik. Devam etmek için Discord’u yeniden bağlayın.",
    errorScope:
      "Discord erişiminde sunucu (guilds) izni eksik. Discord’u yeniden bağlayın ve istenen tüm izinleri onaylayın.",
    errorRateLimited:
      "Discord istekleri sınırlıyor. Lütfen biraz bekleyip yeniden deneyin.",
    errorUnavailable: "Discord geçici olarak kullanılamıyor. Lütfen yeniden deneyin.",
    requestId: "Destek referansı: {id}",
    awaitingInstall: "{name} sunucusuna NorBot’un katılması bekleniyor…",
    installTimedOut:
      "{name} için kurulum hâlâ görünmüyor. Discord’da tamamladıysanız yenileyin veya Yükle’yi tekrar açın.",
    pageOf: "Sayfa {page} / {pages}",
    previousPage: "Önceki",
    nextPage: "Sonraki",
  },
};

function messageForCode(copy: ServersCopy, code: string): string {
  switch (code) {
    case "discord_scope_missing":
      return copy.errorScope;
    case "discord_token_invalid":
    case "discord_token_missing":
    case "authentication_required":
      return copy.errorAuth;
    case "discord_rate_limited":
      return copy.errorRateLimited;
    case "discord_unavailable":
      return copy.errorUnavailable;
    default:
      return copy.errorGeneric;
  }
}

function normalizeServer(raw: ServerGuildItem): ServerGuildItem {
  // bot_installed is the selector SoT; setup_state is derived for compatibility.
  const setupState = resolveSetupState({
    bot_installed: Boolean(raw.bot_installed),
    setup_state: raw.setup_state,
  });
  const botInstalled = setupState === "installed";
  return {
    ...raw,
    id: String(raw.id),
    bot_installed: botInstalled,
    setup_state: setupState,
  };
}

function sortServers(list: ServerGuildItem[]): ServerGuildItem[] {
  return [...list].sort((a, b) => {
    const aInstalled = a.bot_installed ? 0 : 1;
    const bInstalled = b.bot_installed ? 0 : 1;
    if (aInstalled !== bInstalled) return aInstalled - bInstalled;
    return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
  });
}

function ServerGridSkeleton() {
  return (
    <div
      className="norgoth-server-grid-scroll norgoth-scrollbar"
      style={{ flex: "1 1 auto", minHeight: 0 }}
      aria-hidden="true"
    >
      <div className="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-3 pb-2">
        {Array.from({ length: 6 }, (_, index) => (
          <div className="col" key={index}>
            <div className="norgoth-mini-card norgoth-server-guild-card p-3 d-flex flex-column gap-3">
              <div className="d-flex align-items-center gap-3">
                <div
                  className="norgoth-skeleton rounded-circle flex-shrink-0"
                  style={{ width: 40, height: 40 }}
                />
                <div className="flex-grow-1 d-flex flex-column gap-2">
                  <div
                    className="norgoth-skeleton"
                    style={{ height: 14, width: "70%" }}
                  />
                  <div
                    className="norgoth-skeleton"
                    style={{ height: 12, width: "40%" }}
                  />
                </div>
              </div>
              <div
                className="norgoth-skeleton align-self-end"
                style={{ height: 40, width: 120 }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ServerSelector({ copy }: { copy?: Partial<ServersCopy> }) {
  const params = useParams();
  const lang = String(params?.lang ?? "en");
  const locale = lang === "tr" ? "tr" : "en";
  const t = useMemo<ServersCopy>(
    () => ({ ...FALLBACK_COPY[locale], ...copy }),
    [locale, copy],
  );
  const router = useRouter();
  const selectGuild = useGuildStore((s) => s.selectGuild);
  const selectedGuildId = useGuildStore((s) => s.selectedGuild?.id);
  const [servers, setServers] = useState<ServerGuildItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [page, setPage] = useState(1);
  const [awaitingGuildId, setAwaitingGuildId] = useState<string | null>(null);
  const [awaitingGuildName, setAwaitingGuildName] = useState<string | null>(
    null,
  );
  const [awaitingStartedAt, setAwaitingStartedAt] = useState<number | null>(
    null,
  );
  const [installTimedOut, setInstallTimedOut] = useState(false);
  const gridRef = useRef<HTMLDivElement | null>(null);

  const reconnectHref = browserApiUrl(
    `/api/v1/oauth/discord/dashboard/authorize?lang=${encodeURIComponent(lang)}`,
  );

  const loadServers = useCallback(
    async (opts?: { quiet?: boolean }) => {
      if (!opts?.quiet) {
        setLoading(true);
      }
      setError(null);
      setErrorCode(null);
      setRequestId(null);
      try {
        const response = await fetch(apiUrl("/api/v1/sessions/servers"), {
          cache: "no-store",
          credentials: "include",
        });
        if (!response.ok) {
          const apiError = await readApiError(response);
          setErrorCode(apiError.code);
          setRequestId(apiError.requestId);
          setError(messageForCode(t, apiError.code));
          setServers([]);
          setPage(1);
          return;
        }
        const data = (await response.json()) as { servers: ServerGuildItem[] };
        const next = sortServers((data.servers ?? []).map(normalizeServer));
        setServers(next);
      } catch {
        setErrorCode("http_error");
        setError(t.errorGeneric);
        setServers([]);
        setPage(1);
      } finally {
        if (!opts?.quiet) {
          setLoading(false);
        }
      }
    },
    [t],
  );

  useEffect(() => {
    void loadServers();
  }, [loadServers, reloadKey, lang, router]);

  // Clear awaiting when the target guild becomes installed.
  useEffect(() => {
    if (!awaitingGuildId) return;
    const target = servers.find((s) => s.id === awaitingGuildId);
    if (target?.bot_installed) {
      setAwaitingGuildId(null);
      setAwaitingStartedAt(null);
      setInstallTimedOut(false);
    }
  }, [servers, awaitingGuildId]);

  // Poll while awaiting install (visibility + interval).
  useEffect(() => {
    if (!awaitingGuildId || awaitingStartedAt == null) return;

    const tick = () => {
      if (document.visibilityState === "hidden") return;
      if (Date.now() - awaitingStartedAt >= INSTALL_POLL_MAX_MS) {
        setInstallTimedOut(true);
        setAwaitingGuildId(null);
        setAwaitingStartedAt(null);
        return;
      }
      void loadServers({ quiet: true });
    };

    const onVisibility = () => {
      if (document.visibilityState === "visible") tick();
    };

    document.addEventListener("visibilitychange", onVisibility);
    const interval = window.setInterval(tick, INSTALL_POLL_MS);
    tick();
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.clearInterval(interval);
    };
  }, [awaitingGuildId, awaitingStartedAt, loadServers]);

  const totalPages = Math.max(1, Math.ceil(servers.length / PAGE_SIZE));
  const safePage = Math.min(Math.max(1, page), totalPages);
  useEffect(() => {
    if (page !== safePage) setPage(safePage);
  }, [page, safePage]);

  const pageServers = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return servers.slice(start, start + PAGE_SIZE);
  }, [servers, safePage]);

  function goToPage(next: number) {
    setPage(next);
    requestAnimationFrame(() => {
      gridRef.current?.focus();
    });
  }

  async function openServer(server: ServerGuildItem) {
    if (!server.bot_installed || server.setup_state === "not_installed") {
      return;
    }
    const guild: SelectedGuild = {
      id: server.id,
      name: server.name,
      icon: server.icon ?? null,
      icon_url: server.icon_url,
      bot_installed: true,
    };
    await selectGuild(guild);
    router.push(`/${lang}/dashboard`);
  }

  const startAwaitingInstall = useCallback((server: ServerGuildItem) => {
    setAwaitingGuildName(server.name);
    setAwaitingGuildId(server.id);
    setAwaitingStartedAt(null);
    setInstallTimedOut(false);
  }, []);

  // Stamp poll start time in an effect (Date.now is impure during render/handlers under react-hooks/purity).
  useEffect(() => {
    if (!awaitingGuildId || awaitingStartedAt != null) return;
    setAwaitingStartedAt(Date.now());
  }, [awaitingGuildId, awaitingStartedAt]);

  const showReconnect = errorCode ? isReconnectErrorCode(errorCode) : false;
  const showRetry = errorCode ? isRetryErrorCode(errorCode) : Boolean(error);
  const awaitingServer = awaitingGuildId
    ? servers.find((s) => s.id === awaitingGuildId)
    : null;
  const timedOutName = awaitingGuildName ?? "server";
  const pageLabel = t.pageOf
    .replace("{page}", String(safePage))
    .replace("{pages}", String(totalPages));

  return (
    <CContainer
      fluid
      className="norgoth-server-selector-content py-4 d-flex flex-column"
      style={{ maxWidth: 1180, minHeight: 0, flex: "1 1 auto" }}
    >
      <PageHeader
        title={t.title}
        description={t.subtitle}
        actions={
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              setInstallTimedOut(false);
              setReloadKey((key) => key + 1);
            }}
          >
            {t.refresh}
          </Button>
        }
      />

      {awaitingServer ? (
        <p className="small text-body-secondary mb-3 flex-shrink-0" role="status">
          {t.awaitingInstall.replace("{name}", awaitingServer.name)}
        </p>
      ) : null}

      {installTimedOut ? (
        <div className="mb-3 flex-shrink-0">
          <p className="text-warning mb-2" role="status">
            {t.installTimedOut.replace("{name}", timedOutName)}
          </p>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              setInstallTimedOut(false);
              setReloadKey((key) => key + 1);
            }}
          >
            {t.retry}
          </Button>
        </div>
      ) : null}

      {loading ? (
        <>
          <p className="visually-hidden" role="status">
            {t.loading}
          </p>
          <ServerGridSkeleton />
        </>
      ) : null}

      {error ? (
        <div className="mb-3">
          <p className="text-danger mb-2">{error}</p>
          {requestId ? (
            <p className="small text-body-secondary mb-2">
              {t.requestId.replace("{id}", requestId)}
            </p>
          ) : null}
          <div className="d-flex flex-wrap gap-2">
            {showReconnect ? (
              <Button asChild variant="primary">
                <a href={reconnectHref}>{t.reconnect}</a>
              </Button>
            ) : null}
            {showRetry ? (
              <Button
                type="button"
                variant="secondary"
                onClick={() => setReloadKey((key) => key + 1)}
              >
                {t.retry}
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}

      {!loading && !error && servers.length > 0 ? (
        <>
          <div
            ref={gridRef}
            tabIndex={-1}
            className="norgoth-server-grid-scroll norgoth-scrollbar"
            style={{ flex: "1 1 auto", minHeight: 0 }}
            aria-label={t.available}
          >
            <div className="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-3 pb-2">
              {pageServers.map((server) => (
                <div className="col" key={server.id}>
                  <ServerGuildCard
                    server={server}
                    selected={server.id === selectedGuildId}
                    copy={t}
                    onOpen={(item) => void openServer(item)}
                    onInstall={startAwaitingInstall}
                  />
                </div>
              ))}
            </div>
          </div>

          {servers.length > PAGE_SIZE ? (
            <div className="d-flex align-items-center justify-content-center gap-3 flex-wrap norgoth-pagination-bar mt-3 flex-shrink-0">
              <div className="d-flex align-items-center gap-2">
                <CButton
                  color="secondary"
                  variant="outline"
                  size="sm"
                  className="norgoth-pagination-btn"
                  disabled={safePage <= 1}
                  onClick={() => goToPage(safePage - 1)}
                >
                  {t.previousPage}
                </CButton>
                <CPagination
                  className="mb-0 norgoth-pagination"
                  aria-label={pageLabel}
                >
                  <CPaginationItem active aria-current="page">
                    {safePage} / {totalPages}
                  </CPaginationItem>
                </CPagination>
                <CButton
                  color="secondary"
                  variant="outline"
                  size="sm"
                  className="norgoth-pagination-btn"
                  disabled={safePage >= totalPages}
                  onClick={() => goToPage(safePage + 1)}
                >
                  {t.nextPage}
                </CButton>
              </div>
            </div>
          ) : null}
        </>
      ) : null}

      {!loading && !error && servers.length === 0 ? (
        <p className="text-body-secondary mt-3">{t.empty}</p>
      ) : null}
    </CContainer>
  );
}
