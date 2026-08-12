import Link from "next/link";
import { notFound } from "next/navigation";
import {
  cilMediaPlay,
  cilSend,
  cilSpeedometer,
} from "@coreui/icons";
import { CAlert, CCol, CRow } from "@/components/ui/coreui";
import { PageHeader } from "@/components/layout/page-header";
import { DashboardAutoRefresh } from "@/components/dashboard/dashboard-auto-refresh";
import { HomeVerificationMetric } from "@/components/dashboard/home-verification-metric";
import { ActivitySummary } from "@/components/dashboard/activity-summary";
import { EngagementChart } from "@/components/dashboard/engagement-chart";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { MetricWidget } from "@/components/ui/metric-widget";
import { apiUrl } from "@/lib/api";
import { hasLocale } from "../../dictionaries";

type HomeStatus = {
  botConnected: boolean;
  guildName: string | null;
  guildId: string | null;
  workerOnline: boolean;
  queuePaused: boolean;
  queuedCount: number;
};

async function fetchJson(path: string): Promise<Record<string, unknown> | null> {
  try {
    const response = await fetch(apiUrl(path), {
      cache: "no-store",
    });

    if (!response.ok) return null;

    return (await response.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

async function getHomeStatus(): Promise<HomeStatus> {
  const [botHealth, workerHealth, queueState] = await Promise.all([
    fetchJson("/bot/health"),
    fetchJson("/campaigns/worker/health"),
    fetchJson("/campaigns/queue/state"),
  ]);

  const status = (botHealth?.status ?? {}) as {
    guilds?: { id: string; name: string }[];
  };
  const guild = status.guilds?.[0] ?? null;

  return {
    botConnected: Boolean(botHealth?.connected),
    guildName: guild?.name ?? null,
    guildId: guild?.id ?? null,
    workerOnline: Boolean(workerHealth?.online),
    queuePaused: Boolean(queueState?.is_paused),
    queuedCount: Number(queueState?.queued_count ?? 0),
  };
}

export default async function DashboardPage({
  params,
}: PageProps<"/[lang]/dashboard">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  const status = await getHomeStatus();

  const quickActions = [
    {
      title: "Create Campaign",
      description: "Send a message to a Discord channel through the bot.",
      href: "/campaigns/new",
    },
    {
      title: "Verification Settings",
      description: "Channels, roles, and policy for member verification.",
      href: "/community/onboarding",
    },
    {
      title: "Welcome & Leave Messages",
      description: "Greet new members and post a message when they leave.",
      href: "/automation/welcome-goodbye-invite",
    },
    {
      title: "Bot Runtime",
      description: "Gateway status, latency, intents, and servers.",
      href: "/settings/bot-runtime",
    },
  ];

  return (
    <>
      <DashboardAutoRefresh />

      <div className="d-flex flex-column gap-4">
        <PageHeader
          title="NorBot"
          category="dashboard"
          icon={<Icon icon={cilSpeedometer} size="xl" />}
          description={
            status.guildName
              ? `Managing ${status.guildName}`
              : "Discord community management: verification, moderation, campaigns, and onboarding."
          }
          actions={
            <Button asChild variant="primary">
              <Link href={`/${lang}/campaigns/new`}>
                <span className="d-inline-flex align-items-center gap-2">
                  <Icon icon={cilSend} />
                  Create Campaign
                </span>
              </Link>
            </Button>
          }
        />

        <CRow className="g-2">
          <CCol md={6} xl={3}>
            <Link
              href={`/${lang}/settings/bot-runtime`}
              className="text-decoration-none d-block h-100"
            >
              <MetricWidget
                label="Bot"
                value={status.botConnected ? "Connected" : "Offline"}
                accent={status.botConnected ? "success" : "danger"}
                helper={
                  status.botConnected
                    ? status.guildName ?? "Online"
                    : "Start apps/bot with a token"
                }
                icon={<Icon icon={cilMediaPlay} size="lg" />}
              />
            </Link>
          </CCol>
          <CCol md={6} xl={3}>
            <Link
              href={`/${lang}/observability/worker-health`}
              className="text-decoration-none d-block h-100"
            >
              <MetricWidget
                label="Queue"
                value={status.queuePaused ? "Paused" : "Running"}
                accent={status.queuePaused ? "warning" : "success"}
                helper={`${status.queuedCount} campaign(s) queued`}
                icon={<Icon icon={cilSend} size="lg" />}
              />
            </Link>
          </CCol>
          <CCol md={6} xl={3}>
            <Link
              href={`/${lang}/observability/worker-health`}
              className="text-decoration-none d-block h-100"
            >
              <MetricWidget
                label="Campaign Worker"
                value={status.workerOnline ? "Online" : "Offline"}
                accent={status.workerOnline ? "success" : "danger"}
                helper="Delivers campaign messages"
                icon={<Icon icon={cilMediaPlay} size="lg" />}
              />
            </Link>
          </CCol>
          <CCol md={6} xl={3}>
            <HomeVerificationMetric lang={lang} />
          </CCol>
        </CRow>

        {!status.botConnected && (
          <CAlert color="warning" className="mb-0">
            <h2 className="h5">Finish setup: bring the bot online</h2>
            <p className="mb-0">
              Add <code>DISCORD_BOT_TOKEN</code> to <code>Norgoth/.env</code>,
              start the bot (<code>apps/bot</code>), and invite it to your
              server. Every feature on this dashboard activates automatically
              once the bot connects.
            </p>
          </CAlert>
        )}

        <CRow className="g-3">
          {quickActions.map((action) => (
            <CCol key={action.href} md={6} xl={3}>
              <Link
                href={`/${lang}${action.href}`}
                className="text-decoration-none"
              >
                <Card variant="interactive" className="h-100">
                  <div className="d-flex align-items-start justify-content-between gap-2">
                    <div className="min-w-0">
                      <div className="fw-semibold">{action.title}</div>
                      <p className="mt-1 mb-0 small text-body-secondary">
                        {action.description}
                      </p>
                    </div>
                    <span className="small fw-medium text-nowrap">Open →</span>
                  </div>
                </Card>
              </Link>
            </CCol>
          ))}
        </CRow>

        <CRow className="g-3">
          <CCol xl={7}>
            <EngagementChart />
          </CCol>
          <CCol xl={5}>
            <ActivitySummary />
          </CCol>
        </CRow>
      </div>
    </>
  );
}
