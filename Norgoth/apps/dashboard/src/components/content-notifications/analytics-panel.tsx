"use client";

import { useEffect } from "react";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useContentNotificationsStore } from "@/stores/content-notifications-store";

export function AnalyticsPanel() {
  const { guildId } = useFirstGuild();
  const analytics = useContentNotificationsStore((s) => s.analytics);
  const loadAnalytics = useContentNotificationsStore((s) => s.loadAnalytics);

  useEffect(() => {
    if (guildId) void loadAnalytics(guildId);
  }, [guildId, loadAnalytics]);

  if (!analytics) {
    return <p className="text-body-secondary mb-0">Loading analytics…</p>;
  }

  return (
    <div className="d-flex flex-column gap-4">
      <div className="row g-3">
        <div className="col-6 col-md-3">
          <Metric
            label="Delivery success"
            value={`${Math.round(analytics.delivery_success_rate * 100)}%`}
          />
        </div>
        <div className="col-6 col-md-3">
          <Metric label="Sent" value={String(analytics.notifications_sent)} />
        </div>
        <div className="col-6 col-md-3">
          <Metric
            label="Failed"
            value={String(analytics.failed_notifications)}
          />
        </div>
        <div className="col-6 col-md-3">
          <Metric
            label="Avg latency"
            value={`${analytics.average_delivery_latency_ms} ms`}
          />
        </div>
      </div>

      <div className="border rounded p-3">
        <h3 className="h6">Platform distribution</h3>
        {analytics.platform_distribution.length === 0 ? (
          <p className="small text-body-secondary mb-0">No data yet.</p>
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
        Worker: {analytics.worker_online ? "online" : "offline"}
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
