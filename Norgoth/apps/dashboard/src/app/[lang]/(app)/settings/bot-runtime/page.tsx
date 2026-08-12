import Link from "next/link";
import { notFound } from "next/navigation";
import { CAlert, CCol, CRow } from "@/components/ui/coreui";
import { PageHeader } from "@/components/layout/page-header";
import { DashboardAutoRefresh } from "@/components/dashboard/dashboard-auto-refresh";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiUrl } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import { getDictionary, hasLocale } from "../../../dictionaries";

type BotGuild = {
  id: string;
  name: string;
  member_count?: number | null;
};

type BotHealth = {
  connected: boolean;
  heartbeat_at?: string | null;
  status: {
    user_name?: string | null;
    user_id?: string | null;
    application_id?: string | null;
    latency_ms?: number | null;
    intents?: Record<string, boolean>;
    guilds?: BotGuild[];
    updated_at?: string | null;
  };
};

async function getBotHealth(): Promise<BotHealth | null> {
  try {
    const response = await fetch(apiUrl(`/bot/health`), {
      cache: "no-store",
    });

    if (!response.ok) return null;

    return (await response.json()) as BotHealth;
  } catch {
    return null;
  }
}

export default async function BotRuntimeSettingsPage({
  params,
}: PageProps<"/[lang]/settings/bot-runtime">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);
  const health = await getBotHealth();

  const connected = health?.connected ?? false;
  const status = health?.status ?? {};
  const guilds = status.guilds ?? [];
  const intents = status.intents ?? {};

  return (

    <>
    <DashboardAutoRefresh />

      <div className="d-flex flex-column gap-4">
        <PageHeader
          title="Bot Runtime"
          description="Live connection state of NorBot: gateway status, latency, intents, and connected servers."
          actions={
            <Button asChild variant="secondary">
              <Link href={`/${lang}/settings`}>Back to Settings</Link>
            </Button>
          }
        />

        <CRow className="g-3">
          <CCol md={6} xl={3}>
            <MetricCard
              label="Gateway"
              value={connected ? "Connected" : "Offline"}
              tone={connected ? "success" : "danger"}
            />
          </CCol>
          <CCol md={6} xl={3}>
            <MetricCard
              label="Latency"
              value={
                status.latency_ms != null ? `${status.latency_ms} ms` : "—"
              }
              tone="info"
            />
          </CCol>
          <CCol md={6} xl={3}>
            <MetricCard
              label="Servers"
              value={String(guilds.length)}
              tone="success"
            />
          </CCol>
          <CCol md={6} xl={3}>
            <MetricCard
              label="Last Heartbeat"
              value={formatDateTime(health?.heartbeat_at, lang)}
              tone="neutral"
            />
          </CCol>
        </CRow>

        {!connected && (
          <CAlert color="warning">
            <h2 className="h5 mb-2 fw-semibold">Bot is offline</h2>
            <p className="mb-0 small">
              Set <code>DISCORD_BOT_TOKEN</code> in <code>Norgoth/.env</code>,
              then start the bot with{" "}
              <code>cd Norgoth/apps/bot && .venv/bin/python main.py</code>.
              Invite it to your server with Manage Roles, Kick, Ban, Moderate
              Members, Send Messages, and Manage Messages permissions.
            </p>
          </CAlert>
        )}

        <CRow className="g-4">
          <CCol xl={8}>
            <Card>
              <div className="d-flex flex-column gap-4">
                <div className="d-flex align-items-center justify-content-between gap-3">
                  <div>
                    <h2 className="h5 mb-0 fw-semibold">Connected Servers</h2>
                    <p className="mt-1 mb-0 small text-body-secondary">
                      Guilds the bot is currently a member of.
                    </p>
                  </div>

                  <Badge variant={connected ? "success" : "danger"}>
                    {connected ? "Online" : "Offline"}
                  </Badge>
                </div>

                {guilds.length === 0 ? (
                  <CAlert color="secondary" className="mb-0">
                    No servers yet. Once the bot is online and invited, servers
                    appear here automatically.
                  </CAlert>
                ) : (
                  <div className="d-flex flex-column gap-3">
                    {guilds.map((guild) => (
                      <div key={guild.id} className="border rounded p-3">
                        <div className="d-flex flex-column flex-xl-row align-items-xl-center justify-content-xl-between gap-2">
                          <div>
                            <div className="fw-semibold">{guild.name}</div>
                            <p className="mt-1 mb-0 small text-body-secondary">
                              ID: {guild.id}
                            </p>
                          </div>

                          <Badge variant="success">
                            {guild.member_count ?? "?"} members
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          </CCol>

          <CCol xl={4}>
            <Card>
              <div className="d-flex flex-column gap-3">
                <div>
                  <h2 className="h5 mb-0 fw-semibold">Identity & Intents</h2>
                  <p className="mt-1 mb-0 small text-body-secondary">
                    Gateway identity and privileged intent flags.
                  </p>
                </div>

                <StatusRow
                  label="Bot User"
                  value={status.user_name ?? "—"}
                  tone="info"
                />
                <StatusRow
                  label="Application ID"
                  value={status.application_id ?? "—"}
                  tone="neutral"
                />
                {Object.entries(intents).map(([name, enabled]) => (
                  <StatusRow
                    key={name}
                    label={`Intent: ${name}`}
                    value={enabled ? "Enabled" : "Disabled"}
                    tone={enabled ? "success" : "warning"}
                  />
                ))}
              </div>
            </Card>
          </CCol>
        </CRow>
      </div>
    </>
  );
}

function MetricCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: string;
}) {
  const valueClass =
    tone === "success"
      ? "text-success"
      : tone === "warning"
        ? "text-warning"
        : tone === "danger"
          ? "text-danger"
          : tone === "info"
            ? "text-info"
            : "";

  return (
    <Card>
      <div className="small text-body-secondary">{label}</div>
      <div className={`mt-3 fs-3 fw-semibold ${valueClass}`}>
        {value}
      </div>
    </Card>
  );
}

function StatusRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: string;
}) {
  const valueClass =
    tone === "success"
      ? "text-success"
      : tone === "warning"
        ? "text-warning"
        : tone === "danger"
          ? "text-danger"
          : tone === "info"
            ? "text-info"
            : "";

  return (
    <div className="d-flex align-items-center justify-content-between border rounded px-3 py-2">
      <div className="small text-body-secondary">{label}</div>
      <div className={`small fw-medium ${valueClass}`}>{value}</div>
    </div>
  );
}
