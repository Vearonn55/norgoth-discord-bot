"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { CContainer } from "@coreui/react";
import { apiUrl, browserApiUrl } from "@/lib/api";
import {
  isReconnectErrorCode,
  isRetryErrorCode,
  readApiError,
} from "@/lib/api-error";
import { botInviteHref } from "@/lib/bot-invite";
import { isSetupState } from "@/lib/server-setup-state";
import { useGuildStore, type SelectedGuild } from "@/stores/guild-store";
import { Button } from "@/components/ui/button";
import {
  ServerGuildCard,
  type ServerGuildItem,
} from "@/components/auth/server-guild-card";

type ServersCopy = {
  title: string;
  subtitle: string;
  addBot: string;
  loading: string;
  empty: string;
  available: string;
  notInstalled: string;
  notConfigured: string;
  configured: string;
  open: string;
  continueSetup: string;
  installNorBot: string;
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
};

const FALLBACK_COPY: Record<"en" | "tr", ServersCopy> = {
  en: {
    title: "Your Servers",
    subtitle:
      "Choose a Discord server to manage. Only servers where you have Manage Server or Administrator permission are listed.",
    addBot: "Add NorBot to Discord",
    loading: "Loading servers…",
    empty:
      "No manageable servers found. Make sure you have Manage Server permission, then add NorBot to your Discord server.",
    available: "Available to manage",
    notInstalled: "Not installed",
    notConfigured: "Not configured",
    configured: "Configured",
    open: "Open Command Center",
    continueSetup: "Continue setup",
    installNorBot: "Install NorBot",
    addNorgoth: "Install NorBot",
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
  },
  tr: {
    title: "Sunucularınız",
    subtitle:
      "Yönetmek istediğiniz Discord sunucusunu seçin. Yalnızca Sunucuyu Yönet veya Yönetici izniniz olan sunucular listelenir.",
    addBot: "NorBot’u Discord’a ekle",
    loading: "Sunucular yükleniyor…",
    empty:
      "Yönetilebilir sunucu bulunamadı. Sunucuyu Yönet izniniz olduğundan emin olun, ardından NorBot’u Discord sunucunuza ekleyin.",
    available: "Yönetime hazır",
    notInstalled: "Yüklü değil",
    notConfigured: "Yapılandırılmadı",
    configured: "Yapılandırıldı",
    open: "Komuta Merkezini aç",
    continueSetup: "Kuruluma devam et",
    installNorBot: "NorBot’u yükle",
    addNorgoth: "NorBot’u yükle",
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
  const setupState = isSetupState(raw.setup_state)
    ? raw.setup_state
    : raw.bot_installed
      ? "not_configured"
      : "not_installed";
  return {
    ...raw,
    id: String(raw.id),
    setup_state: setupState,
  };
}

function ServerGridSkeleton() {
  return (
    <div
      className="norgoth-server-grid-scroll"
      style={{ flex: "1 1 auto", minHeight: 0, overflowY: "auto" }}
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
  const t: ServersCopy = { ...FALLBACK_COPY[locale], ...copy };
  const router = useRouter();
  const selectGuild = useGuildStore((s) => s.selectGuild);
  const selectedGuildId = useGuildStore((s) => s.selectedGuild?.id);
  const [servers, setServers] = useState<ServerGuildItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const reconnectHref = browserApiUrl(
    `/api/v1/oauth/discord/dashboard/authorize?lang=${encodeURIComponent(lang)}`,
  );

  const loadServers = useCallback(async () => {
    setLoading(true);
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
        return;
      }
      const data = (await response.json()) as { servers: ServerGuildItem[] };
      setServers((data.servers ?? []).map(normalizeServer));
    } catch {
      setErrorCode("http_error");
      setError(t.errorGeneric);
      setServers([]);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadServers();
  }, [loadServers, reloadKey, lang, router]);

  async function openServer(server: ServerGuildItem) {
    if (server.setup_state === "not_installed" || !server.bot_installed) {
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

  const addBotHref = botInviteHref();
  const showReconnect = errorCode ? isReconnectErrorCode(errorCode) : false;
  const showRetry = errorCode ? isRetryErrorCode(errorCode) : Boolean(error);

  return (
    <CContainer
      fluid
      className="norgoth-server-selector py-4 d-flex flex-column"
      style={{ maxWidth: 1180, minHeight: 0, flex: "1 1 auto" }}
    >
      <div className="d-flex flex-column flex-md-row align-items-md-end justify-content-between gap-3 mb-4 flex-shrink-0">
        <div className="min-w-0">
          <h1 className="h3 mb-2">{t.title}</h1>
          <p className="text-body-secondary mb-0" style={{ maxWidth: 640 }}>
            {t.subtitle}
          </p>
        </div>
        <div className="d-flex flex-wrap gap-2">
          <Button
            type="button"
            variant="secondary"
            onClick={() => setReloadKey((key) => key + 1)}
          >
            {t.refresh}
          </Button>
          <Button asChild variant="secondary">
            <a href={addBotHref}>{t.addBot}</a>
          </Button>
        </div>
      </div>

      {loading ? <ServerGridSkeleton /> : null}

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
        <div
          className="norgoth-server-grid-scroll"
          style={{ flex: "1 1 auto", minHeight: 0, overflowY: "auto" }}
        >
          <div className="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-3 pb-2">
            {servers.map((server) => (
              <div className="col" key={server.id}>
                <ServerGuildCard
                  server={server}
                  selected={server.id === selectedGuildId}
                  copy={t}
                  onOpen={(item) => void openServer(item)}
                />
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {!loading && !error && servers.length === 0 ? (
        <p className="text-body-secondary mt-3">{t.empty}</p>
      ) : null}
    </CContainer>
  );
}


