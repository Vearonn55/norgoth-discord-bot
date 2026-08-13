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
import { formatDateTime } from "@/lib/datetime";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";
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

export function CampaignHistoryTable() {
  const dict = useLocaleDict();
  const d = dict.campaignHistoryPage;
  const params = useParams();
  const lang = String(params?.lang || "en");

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

  const statusLabels: Record<string, string> = {
    draft: d.statusDraft,
    scheduled: d.statusScheduled,
    queued: d.statusQueued,
    running: d.statusRunning,
    completed: d.statusCompleted,
    failed: d.statusFailed,
    stopped: d.statusStopped,
  };

  const statusFilters = [
    { value: "all", label: d.filterAll },
    { value: "draft", label: d.statusDraft },
    { value: "scheduled", label: d.statusScheduled },
    { value: "queued", label: d.statusQueued },
    { value: "running", label: d.statusRunning },
    { value: "completed", label: d.statusCompleted },
    { value: "failed", label: d.statusFailed },
    { value: "stopped", label: d.statusStopped },
  ];

  function campaignName(campaign: Campaign): string {
    return campaign.title || campaign.name || d.untitled;
  }

  function campaignPlatforms(campaign: Campaign): string[] {
    const keys = campaign.platform_results
      ? Object.keys(campaign.platform_results)
      : [];
    if (keys.length === 0) return [d.discord];
    return keys.map((key) => key.charAt(0).toUpperCase() + key.slice(1));
  }

  useEffect(() => {
    void loadCampaigns();
  }, [loadCampaigns]);

  const platformOptions = useMemo(() => {
    const seen = new Set<string>();
    for (const campaign of campaigns) {
      for (const platform of campaignPlatforms(campaign)) seen.add(platform);
    }
    return Array.from(seen).sort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaigns, d.discord]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaigns, query, statusFilter, platformFilter, dateRange, d.untitled, d.discord]);

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
        setError(d.actionFailed);
        return;
      }
      await loadCampaigns();
    } catch {
      setError(d.apiUnreachable);
    } finally {
      setActionId(null);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setActionId(pendingDelete.id);
    const ok = await deleteCampaign(pendingDelete.id);
    if (!ok) setError(d.deleteFailed);
    setPendingDelete(null);
    setActionId(null);
  }

  function renderActions(campaign: Campaign) {
    const status = String(campaign.status) as CampaignStatus;
    const busy = actionId === campaign.id;
    const viewBtn = (
      <Button asChild variant="secondary" size="sm">
        <Link href={`/${lang}/campaigns/${campaign.id}`}>{d.view}</Link>
      </Button>
    );

    if (status === "draft") {
      return (
        <div className="d-flex flex-wrap gap-2 justify-content-end">
          <Button asChild variant="secondary" size="sm">
            <Link href={`/${lang}/campaigns/${campaign.id}/edit`}>{d.edit}</Link>
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={busy}
            onClick={() => void runAction(campaign, "start")}
          >
            {busy ? "…" : d.start}
          </Button>
          <Button
            variant="danger"
            size="sm"
            disabled={busy}
            onClick={() => setPendingDelete(campaign)}
          >
            {d.delete}
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
            {busy ? "…" : d.stop}
          </Button>
        </div>
      );
    }

    return (
      <div className="d-flex justify-content-end">{viewBtn}</div>
    );
  }

  return (
    <Card>
      <div className="d-flex flex-column gap-3">
        <div>
          <h2 className="h5 mb-0 fw-semibold">{d.tableTitle}</h2>
          <p className="mt-1 mb-0 small text-body-secondary">
            {d.tableDescription}
          </p>
        </div>

        {error ? (
          <CAlert color="danger" className="mb-0 py-2 px-3">
            {error}
          </CAlert>
        ) : null}

        {loading ? (
          <div className="d-flex align-items-center gap-2 text-body-secondary">
            <CSpinner size="sm" /> {d.loadingCampaigns}
          </div>
        ) : (
          <DataTable
            columns={[
              {
                key: "created_at",
                header: d.colCreatedAt,
                className: "text-nowrap",
                cell: (row) => formatDateTime(row.created_at, lang),
              },
              {
                key: "name",
                header: d.colName,
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
                header: d.colPlatform,
                cell: (row) => campaignPlatforms(row).join(", "),
              },
              {
                key: "audience",
                header: d.colTotalAudience,
                cell: (row) => (row.audience_count ?? 0).toLocaleString(),
              },
              {
                key: "status",
                header: d.colStatus,
                cell: (row) => (
                  <Badge variant={STATUS_VARIANTS[String(row.status)] ?? "neutral"}>
                    {statusLabels[String(row.status)] ?? String(row.status)}
                  </Badge>
                ),
              },
              {
                key: "actions",
                header: d.colActions,
                className: "text-end",
                cell: (row) => renderActions(row),
              },
            ]}
            rows={filtered}
            rowKey={(row) => row.id}
            emptyMessage={d.emptyFiltered}
            search={query}
            onSearchChange={(value) => {
              setQuery(value);
              setPage(1);
            }}
            searchPlaceholder={d.searchPlaceholder}
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
                  aria-label={d.filterByStatus}
                  style={{ minWidth: 150 }}
                >
                  {statusFilters.map((item) => (
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
                    aria-label={d.filterByPlatform}
                    style={{ minWidth: 140 }}
                  >
                    <option value="all">{d.allPlatforms}</option>
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
        title={d.deleteTitle}
        message={
          pendingDelete
            ? formatDict(d.deleteConfirmMessage, {
                name: campaignName(pendingDelete),
              })
            : ""
        }
        confirmLabel={d.deleteConfirm}
        destructive
        busy={actionId !== null && pendingDelete !== null}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setPendingDelete(null)}
      />
    </Card>
  );
}
