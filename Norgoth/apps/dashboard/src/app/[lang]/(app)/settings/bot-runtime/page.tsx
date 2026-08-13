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

function formatCopy(
  template: string,
  values: Record<string, string | number>,
): string {
  return Object.entries(values).reduce(
    (text, [key, value]) => text.replaceAll(`{${key}}`, String(value)),
    template,
  );
}

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

  const dict = await getDictionary(lang);
  const copy = dict.settingsPage;
  const common = dict.common;
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
          title={copy.botRuntimeTitle}
          description={copy.botRuntimeDescription}
          actions={
            <Button asChild variant="secondary">
              <Link href={`/${lang}/settings`}>{copy.backToSettings}</Link>
            </Button>
          }
        />

        <CRow className="g-3">
          <CCol md={6} xl={3}>
            <MetricCard
              label={copy.gateway}
              value={connected ? common.connected : common.offline}
              tone={connected ? "success" : "danger"}
            />
          </CCol>
          <CCol md={6} xl={3}>
            <MetricCard
              label={copy.latency}
              value={
                status.latency_ms != null ? `${status.latency_ms} ms` : "—"
              }
              tone="info"
            />
          </CCol>
          <CCol md={6} xl={3}>
            <MetricCard
              label={copy.servers}
              value={String(guilds.length)}
              tone="success"
            />
          </CCol>
          <CCol md={6} xl={3}>
            <MetricCard
              label={copy.lastHeartbeat}
              value={formatDateTime(health?.heartbeat_at, lang)}
              tone="neutral"
            />
          </CCol>
        </CRow>

        {!connected && (
          <CAlert color="warning">
            <h2 className="h5 mb-2 fw-semibold">{copy.botOfflineTitle}</h2>
            <p className="mb-0 small">{copy.botOfflineBody}</p>
          </CAlert>
        )}

        <CRow className="g-4">
          <CCol xl={8}>
            <Card>
              <div className="d-flex flex-column gap-4">
                <div className="d-flex align-items-center justify-content-between gap-3">
                  <div>
                    <h2 className="h5 mb-0 fw-semibold">
                      {copy.connectedServers}
                    </h2>
                    <p className="mt-1 mb-0 small text-body-secondary">
                      {copy.connectedServersHelp}
                    </p>
                  </div>

                  <Badge variant={connected ? "success" : "danger"}>
                    {connected ? common.online : common.offline}
                  </Badge>
                </div>

                {guilds.length === 0 ? (
                  <CAlert color="secondary" className="mb-0">
                    {copy.noServersYet}
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
                            {formatCopy(copy.membersCount, {
                              count: guild.member_count ?? "?",
                            })}
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
                  <h2 className="h5 mb-0 fw-semibold">
                    {copy.identityIntents}
                  </h2>
                  <p className="mt-1 mb-0 small text-body-secondary">
                    {copy.identityIntentsHelp}
                  </p>
                </div>

                <StatusRow
                  label={copy.botUser}
                  value={status.user_name ?? "—"}
                  tone="info"
                />
                <StatusRow
                  label={copy.applicationId}
                  value={status.application_id ?? "—"}
                  tone="neutral"
                />
                {Object.entries(intents).map(([name, enabled]) => (
                  <StatusRow
                    key={name}
                    label={formatCopy(copy.intentLabel, { name })}
                    value={
                      enabled ? copy.intentEnabled : copy.intentDisabled
                    }
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
      <div className={`mt-3 fs-3 fw-semibold ${valueClass}`}>{value}</div>
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
