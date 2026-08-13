"use client";

import { useEffect } from "react";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useContentNotificationsStore } from "@/stores/content-notifications-store";
import { useContentNotificationsCopy } from "@/lib/content-notifications-copy";

export function AnalyticsPanel() {
  const copy = useContentNotificationsCopy();
  const { guildId } = useFirstGuild();
  const analytics = useContentNotificationsStore((s) => s.analytics);
  const loadAnalytics = useContentNotificationsStore((s) => s.loadAnalytics);

  useEffect(() => {
    if (guildId) void loadAnalytics(guildId);
  }, [guildId, loadAnalytics]);

  if (!analytics) {
    return <p className="text-body-secondary mb-0">{copy.loadingAnalytics}</p>;
  }

  return (
    <div className="d-flex flex-column gap-4">
      <div className="row g-3">
        <div className="col-6 col-md-3">
          <Metric
            label={copy.metricDeliverySuccess}
            value={`${Math.round(analytics.delivery_success_rate * 100)}%`}
          />
        </div>
        <div className="col-6 col-md-3">
          <Metric
            label={copy.metricSent}
            value={String(analytics.notifications_sent)}
          />
        </div>
        <div className="col-6 col-md-3">
          <Metric
            label={copy.metricFailed}
            value={String(analytics.failed_notifications)}
          />
        </div>
        <div className="col-6 col-md-3">
          <Metric
            label={copy.metricAvgLatency}
            value={`${analytics.average_delivery_latency_ms} ms`}
          />
        </div>
      </div>

      <div className="border rounded p-3">
        <h3 className="h6">{copy.platformDistribution}</h3>
        {analytics.platform_distribution.length === 0 ? (
          <p className="small text-body-secondary mb-0">{copy.noDataYet}</p>
        ) : (
          <ul className="mb-0">
            {analytics.platform_distribution.map((row) => (
              <li key={row.platform}>
                <span className="text-uppercase">{row.platform}</span>: {row.count}
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="small text-body-secondary mb-0">
        {copy.workerLabel.replace(
          "{state}",
          analytics.worker_online ? copy.workerOnline : copy.workerOffline,
        )}
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border rounded p-3 h-100">
      <div className="small text-body-secondary">{label}</div>
      <div className="fs-4 fw-semibold mt-1">{value}</div>
    </div>
  );
}
