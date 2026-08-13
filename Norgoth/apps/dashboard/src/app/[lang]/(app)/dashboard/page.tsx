import Link from "next/link";
import { notFound } from "next/navigation";
import {
  cilMediaPlay,
  cilSend,
  cilSpeedometer,
} from "@coreui/icons";
import { CAlert, CCol, CRow } from "@/components/ui/coreui";
import { PageHeader } from "@/components/layout/page-header";
import { ManagingGuildLabel } from "@/components/layout/managing-guild-label";
import { DashboardAutoRefresh } from "@/components/dashboard/dashboard-auto-refresh";
import { HomeVerificationMetric } from "@/components/dashboard/home-verification-metric";
import { ActivitySummary } from "@/components/dashboard/activity-summary";
import { EngagementChart } from "@/components/dashboard/engagement-chart";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { MetricWidget } from "@/components/ui/metric-widget";
import { apiUrl } from "@/lib/api";
import { getDictionary, hasLocale } from "../../dictionaries";

/** Local template fill — keep this page free of client-module imports. */
function fillTemplate(
  template: string,
  values: Record<string, string | number>,
): string {
  return Object.entries(values).reduce(
    (text, [key, value]) => text.replaceAll(`{${key}}`, String(value)),
    template,
  );
}

type HomeStatus = {
  botConnected: boolean;
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

  return {
    botConnected: Boolean(botHealth?.connected),
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

  const dict = await getDictionary(lang);
  const d = dict.dashboard;
  const status = await getHomeStatus();

  const quickActions = [
    {
      title: d.quickCreateCampaignTitle,
      description: d.quickCreateCampaignDesc,
      href: "/campaigns/new",
    },
    {
      title: d.quickVerificationTitle,
      description: d.quickVerificationDesc,
      href: "/community/onboarding",
    },
    {
      title: d.quickWelcomeTitle,
      description: d.quickWelcomeDesc,
      href: "/automation/welcome-goodbye-invite",
    },
  ];

  return (
    <>
      <DashboardAutoRefresh />

      <div className="d-flex flex-column gap-4">
        <PageHeader
          title={d.title}
          category="dashboard"
          icon={<Icon icon={cilSpeedometer} size="xl" />}
          description={<ManagingGuildLabel />}
          actions={
            <Button asChild variant="primary">
              <Link href={`/${lang}/campaigns/new`}>
                <span className="d-inline-flex align-items-center gap-2">
                  <Icon icon={cilSend} />
                  {d.createCampaign}
                </span>
              </Link>
            </Button>
          }
        />

        <CRow className="g-2">
          <CCol md={6} xl={3}>
            <MetricWidget
              label={d.botLabel}
              value={
                status.botConnected
                  ? dict.common.connected
                  : dict.common.offline
              }
              accent={status.botConnected ? "success" : "danger"}
              helper={
                status.botConnected
                  ? d.botHelperOnline
                  : d.botHelperOffline
              }
              icon={<Icon icon={cilMediaPlay} size="lg" />}
            />
          </CCol>
          <CCol md={6} xl={3}>
            <MetricWidget
              label={d.queueLabel}
              value={
                status.queuePaused ? dict.common.paused : dict.common.running
              }
              accent={status.queuePaused ? "warning" : "success"}
              helper={fillTemplate(d.queueHelper, {
                count: status.queuedCount,
              })}
              icon={<Icon icon={cilSend} size="lg" />}
            />
          </CCol>
          <CCol md={6} xl={3}>
            <MetricWidget
              label={d.workerLabel}
              value={
                status.workerOnline ? dict.common.online : dict.common.offline
              }
              accent={status.workerOnline ? "success" : "danger"}
              helper={d.workerHelper}
              icon={<Icon icon={cilMediaPlay} size="lg" />}
            />
          </CCol>
          <CCol md={6} xl={3}>
            <HomeVerificationMetric lang={lang} />
          </CCol>
        </CRow>

        {!status.botConnected && (
          <CAlert color="warning" className="mb-0">
            <h2 className="h5">{d.setupTitle}</h2>
            <p className="mb-0">{d.setupBody}</p>
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
                    <span className="small fw-medium text-nowrap">
                      {dict.common.openArrow}
                    </span>
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
