"use client";

import { useEffect, useMemo, useState } from "react";
import { apiUrl } from "@/lib/api";


type PlatformResult = {
  sent_count?: number;
  failed_count?: number;
  retry_count?: number;
  permanent_failed_count?: number;
};

type Campaign = {
  id: string;
  title?: string;
  status: string;
  platform_results?: Record<string, PlatformResult>;
};

type HeatmapRow = {
  campaignId: string;
  campaignTitle: string;
  platform: string;
  retry: number;
  failed: number;
  permanentFailed: number;
  intensity: "none" | "low" | "medium" | "high";
};

export function RetryHeatmapPanel() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadCampaigns() {
    try {
      const response = await fetch(apiUrl(`/campaigns`), {
        cache: "no-store",
      });

      if (!response.ok) return;

      const data = await response.json();

      if (Array.isArray(data)) {
        setCampaigns(data);
      } else if (Array.isArray(data.items)) {
        setCampaigns(data.items);
      } else if (Array.isArray(data.campaigns)) {
        setCampaigns(data.campaigns);
      } else {
        setCampaigns([]);
      }
    } catch {
      setCampaigns([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCampaigns();

    const interval = window.setInterval(() => {
      loadCampaigns();
    }, 3000);

    return () => window.clearInterval(interval);
  }, []);

  const rows = useMemo<HeatmapRow[]>(() => {
    const result: HeatmapRow[] = [];

    for (const campaign of campaigns) {
      const platformResults = campaign.platform_results;

      if (!platformResults) continue;

      for (const [platform, metrics] of Object.entries(platformResults)) {
        const retry = Number(metrics.retry_count || 0);
        const failed = Number(metrics.failed_count || 0);
        const permanentFailed = Number(metrics.permanent_failed_count || 0);
        const riskScore = retry + failed + permanentFailed * 2;

        let intensity: HeatmapRow["intensity"] = "none";

        if (riskScore >= 8) {
          intensity = "high";
        } else if (riskScore >= 4) {
          intensity = "medium";
        } else if (riskScore > 0) {
          intensity = "low";
        }

        result.push({
          campaignId: campaign.id,
          campaignTitle: campaign.title || "Untitled Campaign",
          platform,
          retry,
          failed,
          permanentFailed,
          intensity,
        });
      }
    }

    return result.slice(0, 24);
  }, [campaigns]);

  const summary = useMemo(() => {
    return rows.reduce(
      (acc, row) => {
        acc.retry += row.retry;
        acc.failed += row.failed;
        acc.permanentFailed += row.permanentFailed;

        if (row.intensity === "high") acc.highRisk += 1;
        if (row.intensity === "medium") acc.mediumRisk += 1;
        if (row.intensity === "low") acc.lowRisk += 1;

        return acc;
      },
      {
        retry: 0,
        failed: 0,
        permanentFailed: 0,
        highRisk: 0,
        mediumRisk: 0,
        lowRisk: 0,
      },
    );
  }, [rows]);

  return (
    <div className="border rounded p-4">
      <div className="mb-4 d-flex align-items-center justify-content-between gap-3">
        <div>
          <h2 className="h5 mb-0 fw-semibold">
            Retry Heatmap
          </h2>
          <p className="mt-1 small text-body-secondary">
            Platform-level retry, failure, and permanent failure pressure.
          </p>
        </div>

        <div className="d-flex align-items-center gap-2">
          <span
            className="rounded-circle bg-warning d-inline-block"
            style={{ width: 8, height: 8 }}
          />
          <span className="small text-warning">LIVE</span>
        </div>
      </div>

      <div className="mb-4 row g-3">
        <div className="col-6 col-md-3">
          <HeatmapStat label="Retry" value={summary.retry} tone="warning" />
        </div>
        <div className="col-6 col-md-3">
          <HeatmapStat label="Failed" value={summary.failed} tone="danger" />
        </div>
        <div className="col-6 col-md-3">
          <HeatmapStat
            label="Permanent"
            value={summary.permanentFailed}
            tone="danger"
          />
        </div>
        <div className="col-6 col-md-3">
          <HeatmapStat
            label="High Risk"
            value={summary.highRisk}
            tone="danger"
          />
        </div>
      </div>

      {loading ? (
        <div className="border rounded p-4 small text-body-secondary">
          Loading retry heatmap...
        </div>
      ) : rows.length === 0 ? (
        <div className="border rounded p-4 small text-body-secondary">
          No retry heatmap data yet.
        </div>
      ) : (
        <div className="overflow-auto pe-2" style={{ maxHeight: 520 }}>
          <div className="row g-3">
            {rows.map((row) => (
              <div
                key={`${row.campaignId}-${row.platform}`}
                className="col-12 col-md-6 col-xl-4"
              >
                <HeatmapCell row={row} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function HeatmapCell({ row }: { row: HeatmapRow }) {
  const labelClass =
    row.intensity === "high"
      ? "text-danger"
      : row.intensity === "medium"
        ? "text-warning"
        : row.intensity === "low"
          ? "text-info"
          : "text-body-secondary";

  return (
    <div
      className="norgoth-heatmap-cell rounded border p-3 h-100"
      data-intensity={row.intensity}
    >
      <div className="d-flex align-items-start justify-content-between gap-3 mb-3">
        <div>
          <div className="small fw-semibold text-white">
            {row.campaignTitle}
          </div>
          <div className="mt-1 small text-body-secondary text-uppercase">
            {row.platform}
          </div>
        </div>

        <span className={`small fw-semibold text-uppercase ${labelClass}`}>
          {row.intensity}
        </span>
      </div>

      <div className="row g-2 small">
        <div className="col-4">
          <MiniMetric label="Retry" value={row.retry} />
        </div>
        <div className="col-4">
          <MiniMetric label="Failed" value={row.failed} />
        </div>
        <div className="col-4">
          <MiniMetric label="Permanent" value={row.permanentFailed} />
        </div>
      </div>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="border rounded p-2">
      <div className="small text-body-secondary">{label}</div>
      <div className="mt-1 fw-semibold">{value}</div>
    </div>
  );
}

function HeatmapStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "warning" | "danger";
}) {
  const valueClass = tone === "warning" ? "text-warning" : "text-danger";

  return (
    <div className="border rounded p-3 h-100">
      <div className="small text-body-secondary">{label}</div>
      <div className={`mt-2 fs-4 fw-semibold ${valueClass}`}>
        {value}
      </div>
    </div>
  );
}
