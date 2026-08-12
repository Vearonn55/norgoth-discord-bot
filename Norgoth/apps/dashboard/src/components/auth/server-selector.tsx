"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { CContainer, CSpinner } from "@coreui/react";
import { apiUrl, browserApiUrl } from "@/lib/api";
import {
  isReconnectErrorCode,
  isRetryErrorCode,
  readApiError,
} from "@/lib/api-error";
import { botInviteHref } from "@/lib/bot-invite";
import { useGuildStore, type SelectedGuild } from "@/stores/guild-store";
import { Button } from "@/components/ui/button";

type ServerItem = {
  id: string;
  name: string;
  icon_url: string | null;
  bot_installed: boolean;
  manageable: boolean;
};

type ServersCopy = {
  title: string;
  subtitle: string;
  addBot: string;
  loading: string;
  empty: string;
  available: string;
  notInstalled: string;
  open: string;
  addNorgoth: string;
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
    addBot: "Add Norgoth to Discord",
    loading: "Loading servers…",
    empty:
      "No manageable servers found. Make sure you have Manage Server permission, then add Norgoth to your Discord server.",
    available: "Available to manage",
    notInstalled: "Norgoth not installed",
    open: "Open →",
    addNorgoth: "Add Norgoth",
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
    addBot: "Norgoth’u Discord’a ekle",
    loading: "Sunucular yükleniyor…",
    empty:
      "Yönetilebilir sunucu bulunamadı. Sunucuyu Yönet izniniz olduğundan emin olun, ardından Norgoth’u Discord sunucunuza ekleyin.",
    available: "Yönetime hazır",
    notInstalled: "Norgoth yüklü değil",
    open: "Aç →",
    addNorgoth: "Norgoth ekle",
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

function guildInitials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "?";
}

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

export function ServerSelector({ copy }: { copy?: ServersCopy }) {
  const params = useParams();
  const lang = String(params?.lang ?? "en");
  const locale = lang === "tr" ? "tr" : "en";
  const t = copy ?? FALLBACK_COPY[locale];
  const router = useRouter();
  const selectGuild = useGuildStore((s) => s.selectGuild);
  const [servers, setServers] = useState<ServerItem[]>([]);
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
      const data = (await response.json()) as { servers: ServerItem[] };
      setServers(data.servers ?? []);
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

  async function openServer(server: ServerItem) {
    if (!server.bot_installed) return;
    const guild: SelectedGuild = {
      id: server.id,
      name: server.name,
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
      className="py-4 d-flex flex-column"
      style={{ maxWidth: 1180, minHeight: 0, flex: "1 1 auto" }}
    >
      <div className="d-flex flex-column flex-md-row align-items-md-end justify-content-between gap-3 mb-4 flex-shrink-0">
        <div className="min-w-0">
          <h1 className="h3 mb-2">{t.title}</h1>
          <p className="text-body-secondary mb-0" style={{ maxWidth: 640 }}>
            {t.subtitle}
          </p>
        </div>
        <Button asChild variant="secondary">
          <a href={addBotHref}>{t.addBot}</a>
        </Button>
      </div>

      {loading ? (
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" /> {t.loading}
        </div>
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
                onClick={() => setReloadKey((k) => k + 1)}
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
                <button
                  type="button"
                  className="norgoth-section-card norgoth-section-card-primary norgoth-card-interactive text-start d-flex flex-column gap-3 p-3 border-0 w-100 h-100"
                  onClick={() => void openServer(server)}
                  style={{ opacity: server.bot_installed ? 1 : 0.85 }}
                >
                  <span className="d-flex align-items-center gap-3 w-100">
                    {server.icon_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={server.icon_url}
                        alt=""
                        width={48}
                        height={48}
                        className="rounded-circle flex-shrink-0"
                      />
                    ) : (
                      <span
                        className="rounded-circle d-inline-flex align-items-center justify-content-center fw-semibold flex-shrink-0"
                        style={{
                          width: 48,
                          height: 48,
                          background: "var(--cui-tertiary-bg)",
                        }}
                      >
                        {guildInitials(server.name)}
                      </span>
                    )}
                    <span className="flex-grow-1 min-w-0">
                      <span className="d-block fw-semibold text-truncate">
                        {server.name}
                      </span>
                      <span className="small text-body-secondary">
                        {server.bot_installed ? t.available : t.notInstalled}
                      </span>
                    </span>
                  </span>
                  <span className="d-flex justify-content-end w-100">
                    {server.bot_installed ? (
                      <span className="small">{t.open}</span>
                    ) : (
                      <a
                        href={botInviteHref(server.id)}
                        className="btn btn-sm btn-primary"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {t.addNorgoth}
                      </a>
                    )}
                  </span>
                </button>
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
