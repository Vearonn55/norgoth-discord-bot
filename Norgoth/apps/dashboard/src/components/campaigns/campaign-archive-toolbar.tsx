"use client";

import { useEffect, useState } from "react";
import { CCol, CRow } from "@coreui/react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiUrl } from "@/lib/api";
import { useLocaleDict } from "@/lib/locale-dict";

type CampaignRecord = {
  id: string;
  title?: string;
  status?: string;
  delivery_target?: string;
  audience_count?: number;
  sent_count?: number;
  failed_count?: number;
  retry_count?: number;
  permanent_failed_count?: number;
  executed_at?: string | null;
  created_at?: string;
  updated_at?: string;
};

const CSV_COLUMNS: Array<[string, (c: CampaignRecord) => string | number]> = [
  ["id", (c) => c.id],
  ["title", (c) => c.title ?? ""],
  ["status", (c) => c.status ?? ""],
  ["delivery_target", (c) => c.delivery_target ?? "channel"],
  ["audience_count", (c) => c.audience_count ?? 0],
  ["sent_count", (c) => c.sent_count ?? 0],
  ["failed_count", (c) => c.failed_count ?? 0],
  ["retry_count", (c) => c.retry_count ?? 0],
  ["permanent_failed_count", (c) => c.permanent_failed_count ?? 0],
  ["executed_at", (c) => c.executed_at ?? ""],
  ["created_at", (c) => c.created_at ?? ""],
  ["updated_at", (c) => c.updated_at ?? ""],
];

function csvEscape(value: string | number): string {
  const text = String(value);

  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }

  return text;
}

/** Live archive metrics + a real CSV export of all campaign records. */
export function CampaignArchiveToolbar() {
  const d = useLocaleDict().campaignHistoryPage;
  const [campaigns, setCampaigns] = useState<CampaignRecord[]>([]);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await fetch(apiUrl(`/campaigns`), {
          cache: "no-store",
        });

        if (!response.ok) return;

        const data = await response.json();

        if (!cancelled && Array.isArray(data)) {
          setCampaigns(data);
        }
      } catch {
        // metrics stay at zero when the API is unreachable
      }
    }

    void load();

    const interval = window.setInterval(load, 10000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  function exportCsv() {
    setExporting(true);

    try {
      const header = CSV_COLUMNS.map(([name]) => name).join(",");
      const rows = campaigns.map((campaign) =>
        CSV_COLUMNS.map(([, getter]) => csvEscape(getter(campaign))).join(","),
      );
      const csv = [header, ...rows].join("\n");

      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `norgoth-campaigns-${new Date().toISOString().slice(0, 10)}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }

  const archived = campaigns.filter((c) =>
    ["completed", "failed", "stopped"].includes(c.status ?? ""),
  );
  const delivered = campaigns.reduce(
    (sum, c) => sum + Number(c.sent_count ?? 0),
    0,
  );
  const failed = campaigns.reduce(
    (sum, c) => sum + Number(c.failed_count ?? 0),
    0,
  );
  const retries = campaigns.reduce(
    (sum, c) => sum + Number(c.retry_count ?? 0),
    0,
  );

  return (
    <div className="d-flex flex-column gap-3">
      <div className="d-flex justify-content-end">
        <Button
          variant="secondary"
          onClick={exportCsv}
          disabled={exporting || campaigns.length === 0}
        >
          {exporting
            ? d.exporting
            : `${d.exportCsv} (${campaigns.length})`}
        </Button>
      </div>

      <CRow className="g-3">
        <CCol md={6} xl={3}>
          <MetricCard label={d.metricArchived} value={archived.length} />
        </CCol>
        <CCol md={6} xl={3}>
          <MetricCard
            label={d.metricDelivered}
            value={delivered}
            tone="success"
          />
        </CCol>
        <CCol md={6} xl={3}>
          <MetricCard
            label={d.metricFailed}
            value={failed}
            tone="warning"
          />
        </CCol>
        <CCol md={6} xl={3}>
          <MetricCard label={d.metricRetries} value={retries} tone="info" />
        </CCol>
      </CRow>
    </div>
  );
}

function MetricCard({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  tone?: string;
}) {
  const valueClass =
    tone === "success"
      ? "text-success"
      : tone === "warning"
        ? "text-warning"
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
