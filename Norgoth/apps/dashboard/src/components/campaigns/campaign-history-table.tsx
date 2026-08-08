"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { CAlert, CFormSelect, CSpinner } from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/ui/data-table";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import {
  DateRangePicker,
  isInDateRange,
} from "@/components/ui/date-range-filter";
import { apiUrl } from "@/lib/api";
import {
  useCampaignsStore,
  type Campaign,
  type CampaignStatus,
} from "@/stores/campaigns-store";

type BadgeVariant = "neutral" | "success" | "warning" | "danger" | "info";

const STATUS_VARIANTS: Record<string, BadgeVariant> = {
  draft: "neutral",
  scheduled: "info",
  queued: "info",
  running: "warning",
  completed: "success",
  failed: "danger",
  stopped: "warning",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  scheduled: "Scheduled",
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  stopped: "Stopped",
};

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "scheduled", label: "Scheduled" },
  { value: "queued", label: "Queued" },
  { value: "running", label: "Running" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "stopped", label: "Stopped" },
];

function campaignName(campaign: Campaign): string {
  return campaign.title || campaign.name || "Untitled campaign";
}

function campaignPlatforms(campaign: Campaign): string[] {
  const keys = campaign.platform_results
    ? Object.keys(campaign.platform_results)
    : [];
  if (keys.length === 0) return ["Discord"];
  return keys.map((key) => key.charAt(0).toUpperCase() + key.slice(1));
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

export function CampaignHistoryTable() {
  const params = useParams();
  const lang = String(params?.lang ?? "en");

  const campaigns = useCampaignsStore((s) => s.campaigns);
  const loading = useCampaignsStore((s) => s.loading);
  const query = useCampaignsStore((s) => s.query);
  const statusFilter = useCampaignsStore((s) => s.statusFilter);
  const dateRange = useCampaignsStore((s) => s.dateRange);
  const setQuery = useCampaignsStore((s) => s.setQuery);
  const setStatusFilter = useCampaignsStore((s) => s.setStatusFilter);
  const setDateRange = useCampaignsStore((s) => s.setDateRange);
  const loadCampaigns = useCampaignsStore((s) => s.loadCampaigns);
  const deleteCampaign = useCampaignsStore((s) => s.deleteCampaign);

  const [page, setPage] = useState(1);
  const [platformFilter, setPlatformFilter] = useState("all");
  const [actionId, setActionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Campaign | null>(null);

  useEffect(() => {
    void loadCampaigns();
  }, [loadCampaigns]);

  const platformOptions = useMemo(() => {
    const seen = new Set<string>();
    for (const campaign of campaigns) {
      for (const platform of campaignPlatforms(campaign)) seen.add(platform);
    }
    return Array.from(seen).sort();
  }, [campaigns]);

  const filtered = useMemo(() => {
    const search = query.trim().toLowerCase();
    return campaigns
      .filter((campaign) => {
        if (
          statusFilter !== "all" &&
          String(campaign.status) !== statusFilter
        ) {
          return false;
        }
        if (
          platformFilter !== "all" &&
          !campaignPlatforms(campaign).includes(platformFilter)
        ) {
          return false;
        }
        if (
          !isInDateRange(
            campaign.created_at || campaign.executed_at || "",
            dateRange
          )
        ) {
          return false;
        }
        if (!search) return true;
        return campaignName(campaign).toLowerCase().includes(search);
      })
      .sort((a, b) => {
        const aTime = new Date(a.created_at || 0).getTime();
        const bTime = new Date(b.created_at || 0).getTime();
        return bTime - aTime;
      });
  }, [campaigns, query, statusFilter, platformFilter, dateRange]);

  async function runAction(
    campaign: Campaign,
    action: "start" | "stop"
  ) {
    if (actionId) return;
    setActionId(campaign.id);
    setError(null);
    try {
      const response = await fetch(
        apiUrl(`/campaigns/${campaign.id}/${action}`),
        { method: "POST" }
      );
      if (!response.ok) {
        setError("Action failed. Please try again.");
        return;
      }
      await loadCampaigns();
    } catch {
      setError("Could not reach the Norgoth API.");
    } finally {
      setActionId(null);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setActionId(pendingDelete.id);
    const ok = await deleteCampaign(pendingDelete.id);
    if (!ok) setError("Could not delete campaign.");
    setPendingDelete(null);
    setActionId(null);
  }

  function renderActions(campaign: Campaign) {
    const status = String(campaign.status) as CampaignStatus;
    const busy = actionId === campaign.id;
    const viewBtn = (
      <Button asChild variant="secondary" size="sm">
        <Link href={`/${lang}/campaigns/${campaign.id}`}>View</Link>
      </Button>
    );

    if (status === "draft") {
      return (
        <div className="d-flex flex-wrap gap-2 justify-content-end">
          <Button asChild variant="secondary" size="sm">
            <Link href={`/${lang}/campaigns/${campaign.id}/edit`}>Edit</Link>
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={busy}
            onClick={() => void runAction(campaign, "start")}
          >
            {busy ? "…" : "Start"}
          </Button>
          <Button
            variant="danger"
            size="sm"
            disabled={busy}
            onClick={() => setPendingDelete(campaign)}
          >
            Delete
          </Button>
        </div>
      );
    }

    if (status === "running") {
      return (
        <div className="d-flex flex-wrap gap-2 justify-content-end">
          {viewBtn}
          <Button
            variant="danger"
            size="sm"
            disabled={busy}
            onClick={() => void runAction(campaign, "stop")}
          >
            {busy ? "…" : "Stop"}
          </Button>
        </div>
      );
    }

    // scheduled / queued / completed / failed / stopped
    return (
      <div className="d-flex justify-content-end">{viewBtn}</div>
    );
  }

  return (
    <Card>
      <div className="d-flex flex-column gap-3">
        <div>
          <h2 className="h5 mb-0 fw-semibold">Campaign History</h2>
          <p className="mt-1 mb-0 small text-body-secondary">
            All campaigns with delivery status and audience size. Actions adapt
            to each campaign&apos;s state.
          </p>
        </div>

        {error ? (
          <CAlert color="danger" className="mb-0 py-2 px-3">
            {error}
          </CAlert>
        ) : null}

        {loading ? (
          <div className="d-flex align-items-center gap-2 text-body-secondary">
            <CSpinner size="sm" /> Loading campaigns…
          </div>
        ) : (
          <DataTable
            columns={[
              {
                key: "created_at",
                header: "Created At",
                className: "text-nowrap",
                cell: (row) => formatDate(row.created_at),
              },
              {
                key: "name",
                header: "Name",
                cell: (row) => (
                  <Link
                    href={`/${lang}/campaigns/${row.id}`}
                    className="fw-semibold text-decoration-none"
                  >
                    {campaignName(row)}
                  </Link>
                ),
              },
              {
                key: "platform",
                header: "Platform",
                cell: (row) => campaignPlatforms(row).join(", "),
              },
              {
                key: "audience",
                header: "Total Audience",
                cell: (row) => (row.audience_count ?? 0).toLocaleString(),
              },
              {
                key: "status",
                header: "Status",
                cell: (row) => (
                  <Badge variant={STATUS_VARIANTS[String(row.status)] ?? "neutral"}>
                    {STATUS_LABELS[String(row.status)] ?? String(row.status)}
                  </Badge>
                ),
              },
              {
                key: "actions",
                header: "Actions",
                className: "text-end",
                cell: (row) => renderActions(row),
              },
            ]}
            rows={filtered}
            rowKey={(row) => row.id}
            emptyMessage="No campaigns match the current filters."
            search={query}
            onSearchChange={(value) => {
              setQuery(value);
              setPage(1);
            }}
            searchPlaceholder="Search campaigns…"
            page={page}
            pageSize={10}
            onPageChange={setPage}
            toolbar={
              <div className="d-flex align-items-center gap-2 flex-wrap">
                <CFormSelect
                  size="sm"
                  value={statusFilter}
                  onChange={(e) => {
                    setStatusFilter(e.target.value);
                    setPage(1);
                  }}
                  aria-label="Filter by status"
                  style={{ minWidth: 150 }}
                >
                  {STATUS_FILTERS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </CFormSelect>
                {platformOptions.length > 1 ? (
                  <CFormSelect
                    size="sm"
                    value={platformFilter}
                    onChange={(e) => {
                      setPlatformFilter(e.target.value);
                      setPage(1);
                    }}
                    aria-label="Filter by platform"
                    style={{ minWidth: 140 }}
                  >
                    <option value="all">All platforms</option>
                    {platformOptions.map((platform) => (
                      <option key={platform} value={platform}>
                        {platform}
                      </option>
                    ))}
                  </CFormSelect>
                ) : null}
                <DateRangePicker value={dateRange} onChange={setDateRange} />
              </div>
            }
          />
        )}
      </div>

      <ConfirmDialog
        visible={pendingDelete !== null}
        title="Delete campaign"
        message={
          pendingDelete
            ? `Delete "${campaignName(pendingDelete)}"? This cannot be undone.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        busy={actionId !== null && pendingDelete !== null}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setPendingDelete(null)}
      />
    </Card>
  );
}
