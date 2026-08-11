"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { CContainer, CSpinner } from "@coreui/react";
import { apiUrl } from "@/lib/api";
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

function guildInitials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "?";
}

export function ServerSelector() {
  const params = useParams();
  const lang = String(params?.lang ?? "en");
  const router = useRouter();
  const selectGuild = useGuildStore((s) => s.selectGuild);
  const [servers, setServers] = useState<ServerItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const response = await fetch(apiUrl("/api/v1/sessions/servers"), {
          cache: "no-store",
          credentials: "include",
        });
        if (!response.ok) {
          if (response.status === 401) {
            router.replace(`/${lang}/login`);
            return;
          }
          throw new Error("Failed to load servers");
        }
        const data = (await response.json()) as { servers: ServerItem[] };
        if (!cancelled) setServers(data.servers ?? []);
      } catch {
        if (!cancelled) setError("Could not load your Discord servers.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lang, router]);

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

  return (
    <CContainer
      fluid
      className="py-4 d-flex flex-column"
      style={{ maxWidth: 1180, minHeight: 0, flex: "1 1 auto" }}
    >
      {/* Fixed header + primary action */}
      <div className="d-flex flex-column flex-md-row align-items-md-end justify-content-between gap-3 mb-4 flex-shrink-0">
        <div className="min-w-0">
          <h1 className="h3 mb-2">Your Servers</h1>
          <p className="text-body-secondary mb-0" style={{ maxWidth: 640 }}>
            Choose a Discord server to manage. Only servers where you have Manage
            Server or Administrator permission are listed.
          </p>
        </div>
        <Button asChild variant="secondary">
          <a href={addBotHref}>Add Norgoth to Discord</a>
        </Button>
      </div>

      {loading ? (
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" /> Loading servers…
        </div>
      ) : null}

      {error ? <p className="text-danger">{error}</p> : null}

      {/* Single scroll region sized to the remaining viewport space */}
      {!loading && servers.length > 0 ? (
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
                        {server.bot_installed
                          ? "Available to manage"
                          : "Norgoth not installed"}
                      </span>
                    </span>
                  </span>
                  <span className="d-flex justify-content-end w-100">
                    {server.bot_installed ? (
                      <span className="small">Open →</span>
                    ) : (
                      <a
                        href={botInviteHref(server.id)}
                        className="btn btn-sm btn-primary"
                        onClick={(e) => e.stopPropagation()}
                      >
                        Add Norgoth
                      </a>
                    )}
                  </span>
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {!loading && servers.length === 0 ? (
        <p className="text-body-secondary mt-3">
          No manageable servers found. Make sure you have Manage Server
          permission, then add Norgoth to your Discord server.
        </p>
      ) : null}
    </CContainer>
  );
}
