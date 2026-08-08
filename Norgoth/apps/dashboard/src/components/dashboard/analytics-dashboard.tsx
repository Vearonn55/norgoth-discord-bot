"use client";

import Link from "next/link";
import { useEffect, useMemo } from "react";
import { DashboardAutoRefresh } from "@/components/dashboard/dashboard-auto-refresh";
import { RetryHeatmapPanel } from "@/components/dashboard/retry-heatmap-panel";
import { KpiStrip } from "@/components/analytics/kpi-strip";
import { TrendChart } from "@/components/analytics/trend-chart";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CategoryHeader } from "@/components/ui/category-header";
import {
  DateRangePicker,
  isInDateRange,
  type DateRangeValue,
} from "@/components/ui/date-range-filter";
import { SectionCard } from "@/components/ui/section-card";
import {
  computeCommunityKpis,
  computeEngagementMetrics,
  type EngagementRange,
} from "@/lib/analytics/engagement";
import { useFirstGuild } from "@/lib/use-first-guild";
import {
  campaignDateStamp,
  useCampaignsStore,
  type Campaign,
} from "@/stores/campaigns-store";
import { useDashboardStore } from "@/stores/dashboard-store";
import { useGuildStore } from "@/stores/guild-store";

type PlatformAnalytics = {
  platform: string;
  sent: number;
  failed: number;
  retry: number;
  permanentFailed: number;
  successRate: number;
};

type AnalyticsData = {
  sent: number;
  failed: number;
  retries: number;
  permanentFailed: number;
  successRate: number;
  failureRate: number;
  totalCampaigns: number;
  completedCampaigns: number;
  activeCampaigns: number;
  platforms: PlatformAnalytics[];
};

function rangeSpanDays(range: DateRangeValue): number {
  if (!range.start || !range.end) return 7;
  const start = new Date(`${range.start}T12:00:00`);
  const end = new Date(`${range.end}T12:00:00`);
  const diff = Math.round(
    (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)
  );
  return Math.max(0, diff);
}

function closestEngagementRange(range: DateRangeValue): EngagementRange {
  const days = rangeSpanDays(range);
  if (days <= 10) return 7;
  if (days <= 45) return 30;
  return 90;
}

function getPlatformAnalytics(items: Campaign[]): PlatformAnalytics[] {
  const platformMap = new Map<
    string,
    {
      sent: number;
      failed: number;
      retry: number;
      permanentFailed: number;
    }
  >();

  for (const campaign of items) {
    const results = campaign.platform_results;
    if (!results) continue;

    for (const [platform, result] of Object.entries(results)) {
      const current = platformMap.get(platform) || {
        sent: 0,
        failed: 0,
        retry: 0,
        permanentFailed: 0,
      };

      current.sent += Number(result.sent_count || 0);
      current.failed += Number(result.failed_count || 0);
      current.retry += Number(result.retry_count || 0);
      current.permanentFailed += Number(result.permanent_failed_count || 0);

      platformMap.set(platform, current);
    }
  }

  return Array.from(platformMap.entries()).map(([platform, value]) => {
    const total = value.sent + value.failed;
    return {
      platform,
      sent: value.sent,
      failed: value.failed,
      retry: value.retry,
      permanentFailed: value.permanentFailed,
      successRate: total > 0 ? Math.round((value.sent / total) * 100) : 0,
    };
  });
}

function computeAnalytics(items: Campaign[]): AnalyticsData {
  const sent = items.reduce(
    (sum, item) => sum + Number(item.sent_count || 0),
    0
  );
  const failed = items.reduce(
    (sum, item) => sum + Number(item.failed_count || 0),
    0
  );
  const retries = items.reduce(
    (sum, item) => sum + Number(item.retry_count || 0),
    0
  );
  const permanentFailed = items.reduce(
    (sum, item) => sum + Number(item.permanent_failed_count || 0),
    0
  );
  const totalProcessed = sent + failed;

  return {
    sent,
    failed,
    retries,
    permanentFailed,
    successRate:
      totalProcessed > 0 ? Math.round((sent / totalProcessed) * 100) : 0,
    failureRate:
      totalProcessed > 0 ? Math.round((failed / totalProcessed) * 100) : 0,
    totalCampaigns: items.length,
    completedCampaigns: items.filter((item) => item.status === "completed")
      .length,
    activeCampaigns: items.filter((item) =>
      ["queued", "running", "scheduled"].includes(String(item.status))
    ).length,
    platforms: getPlatformAnalytics(items),
  };
}

function campaignTrendByDay(items: Campaign[]): Record<string, string | number>[] {
  const map = new Map<string, { date: string; sent: number; failed: number }>();
  for (const campaign of items) {
    const stamp = campaignDateStamp(campaign);
    if (!stamp) continue;
    const day = stamp.slice(0, 10);
    const current = map.get(day) ?? { date: day.slice(5), sent: 0, failed: 0 };
    current.sent += Number(campaign.sent_count || 0);
    current.failed += Number(campaign.failed_count || 0);
    map.set(day, current);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([, v]) => v);
}

export function AnalyticsDashboard({ lang }: { lang: string }) {
  const campaigns = useCampaignsStore((s) => s.campaigns);
  const dateRange = useCampaignsStore((s) => s.dateRange);
  const setDateRange = useCampaignsStore((s) => s.setDateRange);
  const loadCampaigns = useCampaignsStore((s) => s.loadCampaigns);

  const { guildId } = useFirstGuild();
  const memberCount = useGuildStore((s) => s.resources?.member_count ?? null);
  const engagement = useDashboardStore((s) => s.engagement);
  const loadEngagement = useDashboardStore((s) => s.loadEngagement);

  useEffect(() => {
    void loadCampaigns();
  }, [loadCampaigns]);

  useEffect(() => {
    if (!guildId) return;
    void loadEngagement(guildId, closestEngagementRange(dateRange));
  }, [guildId, dateRange, loadEngagement]);

  const filteredCampaigns = useMemo(
    () =>
      campaigns.filter((campaign) =>
        isInDateRange(campaignDateStamp(campaign), dateRange)
      ),
    [campaigns, dateRange]
  );

  const analyticsData = useMemo(
    () => computeAnalytics(filteredCampaigns),
    [filteredCampaigns]
  );

  const engagementMetrics = useMemo(() => {
    if (!engagement || engagement.insufficient_history) return null;
    return computeEngagementMetrics(engagement.totals, memberCount);
  }, [engagement, memberCount]);

  const communityKpis = useMemo(() => {
    if (!engagement || engagement.insufficient_history) return null;
    return computeCommunityKpis(engagement.totals, memberCount);
  }, [engagement, memberCount]);

  const campaignTrend = useMemo(
    () => campaignTrendByDay(filteredCampaigns),
    [filteredCampaigns]
  );

  const engagementTrend = useMemo(() => {
    if (!engagement || engagement.insufficient_history) return [];
    return engagement.series
      .filter((p) => isInDateRange(`${p.date}T12:00:00.000Z`, dateRange))
      .map((p) => ({
        date: p.date.slice(5),
        messages: p.messages,
        authors: p.unique_authors,
        joins: p.joins,
      }));
  }, [engagement, dateRange]);

  const recentCampaigns = useMemo(() => {
    return [...filteredCampaigns]
      .sort((a, b) => {
        const aTime = new Date(campaignDateStamp(a) || "").getTime();
        const bTime = new Date(campaignDateStamp(b) || "").getTime();
        return bTime - aTime;
      })
      .slice(0, 8);
  }, [filteredCampaigns]);

  return (
    <>
      <DashboardAutoRefresh />

      <div className="d-flex flex-column gap-3">
        <PageHeader
          title="Analytics"
          category="analytics"
          description="Campaign delivery and community engagement from live data."
          actions={
            <>
              <Button asChild variant="secondary">
                <Link href={`/${lang}/campaigns/history`}>Campaign History</Link>
              </Button>
              <Button asChild variant="primary">
                <Link href={`/${lang}/observability/worker-health`}>
                  Worker Health
                </Link>
              </Button>
            </>
          }
        />

        <SectionCard level="secondary">
          <div className="d-flex flex-wrap align-items-end justify-content-between gap-3">
            <div>
              <div className="fw-semibold">Date range</div>
              <p className="mb-0 small text-body-secondary">
                Filters campaign aggregates. Engagement loads the nearest 7 / 30
                / 90 day bucket.
              </p>
            </div>
            <DateRangePicker value={dateRange} onChange={setDateRange} />
          </div>
        </SectionCard>

        <KpiStrip
          items={[
            {
              key: "success",
              label: "Delivery success",
              value: `${analyticsData.successRate}%`,
              helper: `${analyticsData.sent} sent · ${analyticsData.failed} failed`,
              tone:
                analyticsData.successRate >= 90
                  ? "success"
                  : analyticsData.totalCampaigns
                    ? "warning"
                    : "default",
            },
            {
              key: "campaigns",
              label: "Campaigns",
              value: analyticsData.totalCampaigns,
              helper: `${analyticsData.activeCampaigns} active`,
              tone: "info",
            },
            {
              key: "retries",
              label: "Retries",
              value: analyticsData.retries,
              helper: `${analyticsData.permanentFailed} permanent fails`,
              tone: analyticsData.retries > 0 ? "warning" : "success",
            },
            {
              key: "engagement",
              label: "Engagement score",
              value:
                engagementMetrics != null
                  ? Math.round(engagementMetrics.score)
                  : "—",
              helper: engagement?.insufficient_history
                ? "No telemetry yet"
                : engagement
                  ? `${engagement.totals.messages} msgs`
                  : "Guild required",
              tone: engagementMetrics ? "success" : "default",
            },
          ]}
        />

        <CategoryHeader
          category="analytics"
          title="Important trends"
          description="Campaign delivery by day and community message activity."
          as="h3"
        />

        <div className="row g-3">
          <div className="col-xl-6">
            <SectionCard level="primary" category="campaigns">
              <h3 className="h6 fw-semibold mb-3">Campaign delivery</h3>
              <TrendChart
                data={campaignTrend}
                xKey="date"
                series={[
                  { key: "sent", label: "Sent", color: "#3dd68c" },
                  { key: "failed", label: "Failed", color: "#ff6b7a" },
                ]}
                emptyMessage="No campaign delivery points in this range."
              />
            </SectionCard>
          </div>
          <div className="col-xl-6">
            <SectionCard level="primary" category="community">
              <h3 className="h6 fw-semibold mb-3">Community engagement</h3>
              <TrendChart
                data={engagementTrend}
                xKey="date"
                series={[
                  { key: "messages", label: "Messages", color: "#6ea8fe" },
                  { key: "authors", label: "Authors", color: "#3dd68c" },
                  { key: "joins", label: "Joins", color: "#fbbf24" },
                ]}
                emptyMessage="No engagement history yet — buckets fill while the bot is online."
              />
            </SectionCard>
          </div>
        </div>

        <CategoryHeader
          category="community"
          title="Community KPIs"
          description="Derived from live engagement telemetry over the selected window."
          as="h3"
        />
        <KpiStrip
          items={[
            {
              key: "engagement-rate",
              label: "Engagement rate",
              value:
                communityKpis?.engagementRate != null
                  ? `${Math.round(communityKpis.engagementRate)}%`
                  : "—",
              helper:
                communityKpis?.engagementRate != null
                  ? `${communityKpis.activeMembers} active / ${memberCount ?? "?"} members`
                  : engagement?.insufficient_history
                    ? "No telemetry yet"
                    : "Member count required",
              tone: communityKpis?.engagementRate != null ? "info" : "default",
            },
            {
              key: "msgs-per-member",
              label: "Msgs / active member",
              value:
                communityKpis != null
                  ? communityKpis.messagesPerActiveMember.toFixed(1)
                  : "—",
              helper: engagement
                ? `${engagement.totals.messages} msgs · ${communityKpis?.activeMembers ?? 0} authors`
                : "Guild required",
              tone: communityKpis ? "success" : "default",
            },
            {
              key: "net-growth",
              label: "Net growth",
              value:
                communityKpis != null
                  ? `${communityKpis.netGrowth >= 0 ? "+" : ""}${communityKpis.netGrowth}`
                  : "—",
              helper: engagement
                ? `${engagement.totals.joins} joins · ${engagement.totals.leaves} leaves`
                : "Guild required",
              tone:
                communityKpis == null
                  ? "default"
                  : communityKpis.netGrowth >= 0
                    ? "success"
                    : "warning",
            },
            {
              key: "voice-uniques",
              label: "Voice participants",
              value:
                communityKpis != null ? communityKpis.voiceUniques : "—",
              helper: "Unique members in voice",
              tone: "info",
            },
          ]}
        />

        <CategoryHeader
          category="campaigns"
          title="Campaign detail"
          description="Platform delivery and recent campaigns in range."
          as="h3"
        />

        <div className="row g-3">
          <div className="col-xl-5">
            <SectionCard level="secondary">
              <h3 className="h6 fw-semibold mb-3">Platform delivery</h3>
              {analyticsData.platforms.length === 0 ? (
                <p className="mb-0 small text-body-secondary">
                  No platform delivery data yet.
                </p>
              ) : (
                <div className="d-flex flex-column gap-2">
                  {analyticsData.platforms.map((platform) => (
                    <div
                      key={platform.platform}
                      className="d-flex align-items-center justify-content-between gap-2 border rounded px-3 py-2"
                    >
                      <span className="fw-semibold">{platform.platform}</span>
                      <span className="small text-body-secondary">
                        {platform.sent} sent · {platform.failed} failed ·{" "}
                        {platform.successRate}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>
          </div>
          <div className="col-xl-7">
            <SectionCard level="secondary">
              <h3 className="h6 fw-semibold mb-3">Recent campaigns</h3>
              {recentCampaigns.length === 0 ? (
                <p className="mb-0 small text-body-secondary">
                  No campaigns in this date range.
                </p>
              ) : (
                <div className="d-flex flex-column gap-2">
                  {recentCampaigns.map((campaign) => (
                    <Link
                      key={campaign.id}
                      href={`/${lang}/campaigns/${campaign.id}`}
                      className="d-flex flex-wrap align-items-center justify-content-between gap-2 border rounded px-3 py-2 text-decoration-none"
                    >
                      <div className="fw-semibold">
                        {campaign.title || campaign.name || "Untitled Campaign"}
                      </div>
                      <div className="d-flex align-items-center gap-2 small text-body-secondary">
                        <Badge variant="neutral">
                          {String(campaign.status)}
                        </Badge>
                        <span>
                          {campaignDateStamp(campaign)
                            ? new Date(
                                campaignDateStamp(campaign)!
                              ).toLocaleString()
                            : "—"}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </SectionCard>
          </div>
        </div>

        <CategoryHeader
          category="operations"
          title="Diagnostics"
          description="Retry pressure heatmap from campaign delivery."
          as="h3"
        />
        <SectionCard level="secondary">
          <RetryHeatmapPanel />
        </SectionCard>
      </div>
    </>
  );
}
