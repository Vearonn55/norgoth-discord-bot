"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo } from "react";
import { useDashboardStore } from "@/stores/dashboard-store";
import { SectionCard } from "@/components/ui/section-card";
import { Button } from "@/components/ui/button";

/** Compact dashboard activity summary — no nested scroll feed. */
export function ActivitySummary() {
  const params = useParams();
  const lang = String(params?.lang || "en");
  const activities = useDashboardStore((s) => s.activities);
  const loading = useDashboardStore((s) => s.loading);
  const loadActivity = useDashboardStore((s) => s.loadActivity);

  useEffect(() => {
    void loadActivity();
    const interval = window.setInterval(() => void loadActivity(), 15000);
    return () => window.clearInterval(interval);
  }, [loadActivity]);

  const summary = useMemo(() => {
    const latest = activities[0];
    return {
      count: activities.length,
      sent: activities.reduce((n, a) => n + a.sent_count, 0),
      failed: activities.reduce((n, a) => n + a.failed_count, 0),
      latestAt: latest?.created_at ?? null,
    };
  }, [activities]);

  return (
    <SectionCard level="primary" category="operations" className="h-100">
      <div className="d-flex flex-column gap-3 p-1">
        <div>
          <h2 className="h5 mb-1">Recent Activity</h2>
          <p className="mb-0 small text-body-secondary">
            Compact campaign delivery summary. Detailed cross-system history
            lives in the Audit Logs.
          </p>
        </div>

        <div className="row g-2">
          <div className="col-4">
            <div className="border rounded p-2 text-center">
              <div className="fw-semibold">{loading ? "…" : summary.count}</div>
              <div className="small text-body-secondary">Events</div>
            </div>
          </div>
          <div className="col-4">
            <div className="border rounded p-2 text-center">
              <div className="fw-semibold text-success">
                {loading ? "…" : summary.sent}
              </div>
              <div className="small text-body-secondary">Sent</div>
            </div>
          </div>
          <div className="col-4">
            <div className="border rounded p-2 text-center">
              <div className="fw-semibold text-danger">
                {loading ? "…" : summary.failed}
              </div>
              <div className="small text-body-secondary">Failed</div>
            </div>
          </div>
        </div>

        <p className="mb-0 small text-body-secondary">
          {summary.latestAt
            ? `Latest: ${new Date(summary.latestAt).toLocaleString()}`
            : "No recent campaign events yet."}
        </p>

        <Button asChild variant="primary">
          <Link href={`/${lang}/security/logs`}>Open Audit Log</Link>
        </Button>
      </div>
    </SectionCard>
  );
}
