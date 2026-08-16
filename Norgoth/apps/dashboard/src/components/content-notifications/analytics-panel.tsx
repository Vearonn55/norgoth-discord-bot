"use client";

import { useEffect, useMemo, useState } from "react";
import { CAlert, CSpinner } from "@coreui/react";
import { useParams } from "next/navigation";
import { MetricWidget } from "@/components/ui/metric-widget";
import { TrendChart } from "@/components/analytics/trend-chart";
import { StatusBarChart } from "@/components/analytics/status-bar-chart";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useContentNotificationsStore } from "@/stores/content-notifications-store";
import {
  localizeEventType,
  useContentNotificationsCopy,
} from "@/lib/content-notifications-copy";
import { formatNumber } from "@/lib/number";
import { formatDateTime } from "@/lib/datetime";
import {
  PLATFORM_CHART_COLORS,
  prefersReducedMotion,
} from "@/lib/cn-url-state";

function fillSeries(
  series: Array<{ day: string; succeeded: number; failed: number }>,
  rangeStart?: string,
  rangeEnd?: string,
) {
  if (!rangeStart || !rangeEnd) return series;
  const byDay = new Map(series.map((row) => [row.day, row]));
  const start = new Date(rangeStart);
  const end = new Date(rangeEnd);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return series;
  const out: Array<{ day: string; succeeded: number; failed: number }> = [];
  const cursor = new Date(
    Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate()),
  );
  const last = new Date(
    Date.UTC(end.getUTCFullYear(), end.getUTCMonth(), end.getUTCDate()),
  );
  while (cursor <= last) {
    const day = cursor.toISOString().slice(0, 10);
    out.push(byDay.get(day) ?? { day, succeeded: 0, failed: 0 });
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return out;
}

export function AnalyticsPanel() {
  const copy = useContentNotificationsCopy();
  const params = useParams();
  const lang = String(params?.lang || "en");
  const { guildId } = useFirstGuild();
  const analytics = useContentNotificationsStore((s) => s.analytics);
  const error = useContentNotificationsStore((s) => s.error);
  const loadAnalytics = useContentNotificationsStore((s) => s.loadAnalytics);
  const [loading, setLoading] = useState(true);
  const reduceMotion = prefersReducedMotion();

  useEffect(() => {
    if (!guildId) return;
    setLoading(true);
    void loadAnalytics(guildId, 30).finally(() => setLoading(false));
  }, [guildId, loadAnalytics]);

  const filled = useMemo(
    () => fillSeries(analytics?.series ?? [], analytics?.range_start, analytics?.range_end),
    [analytics],
  );
  const series = filled.some((row) => row.succeeded || row.failed) ? filled : [];

  if (loading) {
    return (
      <div className="d-flex align-items-center gap-2 text-body-secondary">
        <CSpinner size="sm" /> {copy.loadingAnalytics}
      </div>
    );
  }

  if (!analytics) {
    return (
      <CAlert color="danger" className="py-2 px-3 mb-0">
        {copy.analyticsError}
      </CAlert>
    );
  }

  const platformRows = (analytics.platform_distribution ?? []).map((row) => ({
    label: row.platform,
    count: row.count,
    color: PLATFORM_CHART_COLORS[row.platform] ?? "#60A5FA",
  }));

  return (
    <div className="d-flex flex-column gap-4">
      {error && !analytics.total_jobs ? (
        <CAlert color="danger" className="py-2 px-3 mb-0">
          {copy.analyticsError}
        </CAlert>
      ) : null}
      <div className="row g-3">
        <div className="col-6 col-md-3">
          <MetricWidget
            label={copy.metricDeliverySuccess}
            value={`${Math.round(analytics.delivery_success_rate * 100)}%`}
            accent="success"
          />
        </div>
        <div className="col-6 col-md-3">
          <MetricWidget
            label={copy.metricSent}
            value={formatNumber(analytics.notifications_sent, lang)}
            accent="primary"
          />
        </div>
        <div className="col-6 col-md-3">
          <MetricWidget
            label={copy.metricFailed}
            value={formatNumber(analytics.failed_notifications, lang)}
            accent="danger"
          />
        </div>
        <div className="col-6 col-md-3">
          <MetricWidget
            label={copy.metricAvgLatency}
            value={`${formatNumber(analytics.average_delivery_latency_ms, lang)} ms`}
            accent="info"
          />
        </div>
      </div>

      <div
        className="border rounded p-3"
        aria-label={copy.notificationsOverTime}
      >
        <h3 className="h6">{copy.notificationsOverTime}</h3>
        <TrendChart
          data={series}
          xKey="day"
          variant="area"
          emptyMessage={copy.noDataYet}
          isAnimationActive={!reduceMotion}
          series={[
            {
              key: "succeeded",
              label: copy.chartSucceeded,
              color: "#34D399",
            },
            { key: "failed", label: copy.chartFailed, color: "#F87171" },
          ]}
        />
      </div>

      <div className="border rounded p-3" aria-label={copy.platformDistribution}>
        <h3 className="h6">{copy.platformDistribution}</h3>
        <StatusBarChart
          data={platformRows}
          emptyMessage={copy.noDataYet}
          isAnimationActive={!reduceMotion}
          ariaLabel={copy.platformDistribution}
        />
        {platformRows.length > 0 ? (
          <ul className="mb-0 mt-3 small">
            {platformRows.map((row) => (
              <li key={row.label}>
                <span className="text-uppercase">{row.label}</span>
                {": "}
                {formatNumber(row.count, lang)}
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      {(analytics.event_type_distribution ?? []).length > 0 ? (
        <ul className="mb-0 small">
          {analytics.event_type_distribution!.map((row) => (
            <li key={row.event_type}>
              {localizeEventType(row.event_type, copy)}
              {": "}
              {formatNumber(row.count, lang)}
            </li>
          ))}
        </ul>
      ) : null}

      {(analytics.recent_failures ?? []).length > 0 ? (
        <div>
          <h3 className="h6">{copy.recentFailures}</h3>
          <ul className="mb-0 small">
            {analytics.recent_failures!.map((row, index) => (
              <li key={`${row.created_at}-${index}`}>
                <span className="text-uppercase">{row.platform}</span>
                {" · "}
                {formatDateTime(row.created_at, lang)}
                {" — "}
                {row.last_error}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="small text-body-secondary mb-0">
        {copy.workerLabel.replace(
          "{state}",
          analytics.worker_online ? copy.workerOnline : copy.workerOffline,
        )}
      </p>
    </div>
  );
}
