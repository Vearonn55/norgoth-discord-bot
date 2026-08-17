"use client";

import { useEffect, useMemo } from "react";
import { useParams } from "next/navigation";
import { CAlert, CButtonGroup, CFormSelect, CSpinner } from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/ui/data-table";
import {
  DateRangePicker,
  defaultDateRange,
  isInDateRange,
  type DateRangeValue,
} from "@/components/ui/date-range-filter";
import { formatDateTime } from "@/lib/datetime";
import { useFeatureInfo } from "@/lib/feature-info";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";
import { useFirstGuild } from "@/lib/use-first-guild";
import { create } from "zustand";
import { AuditChangeDetails } from "@/components/security/audit-change-details";
import { useModerationLogsStore } from "@/stores/moderation-logs-store";
import { useServerEventsStore } from "@/stores/server-events-store";

type AuditSource = "moderation" | "event";

type AuditRow = {
  id: string;
  eventId?: string;
  source: AuditSource;
  category: string;
  action: string;
  summary: string;
  actor: string;
  created_at: string;
  fields: Record<string, string>;
};

const CATEGORY_VARIANTS: Record<
  string,
  "success" | "info" | "warning" | "neutral" | "danger"
> = {
  moderation: "danger",
  member: "success",
  message: "info",
  role: "warning",
  channel: "neutral",
};

type AuditFilterState = {
  source: AuditSource | "all";
  search: string;
  page: number;
  dateRange: DateRangeValue;
  setSource: (value: AuditSource | "all") => void;
  setSearch: (value: string) => void;
  setPage: (page: number) => void;
  setDateRange: (range: DateRangeValue) => void;
};

const useAuditFilterStore = create<AuditFilterState>((set) => ({
  source: "all",
  search: "",
  page: 1,
  dateRange: defaultDateRange(7),
  setSource: (value) => set({ source: value, page: 1 }),
  setSearch: (value) => set({ search: value, page: 1 }),
  setPage: (page) => set({ page }),
  setDateRange: (range) => set({ dateRange: range, page: 1 }),
}));

export function AuditLogsPanel() {
  const params = useParams();
  const lang = String(params?.lang || "en");
  const dict = useLocaleDict();
  const d = dict.auditLogsPage;
  const info = useFeatureInfo("auditLogs");
  const { guildId, loading: guildLoading, error: guildError } = useFirstGuild();

  const modEntries = useModerationLogsStore((s) => s.entries);
  const modLoading = useModerationLogsStore((s) => s.loading);
  const loadModeration = useModerationLogsStore((s) => s.load);

  const eventEntries = useServerEventsStore((s) => s.entries);
  const eventsLoading = useServerEventsStore((s) => s.loading);
  const loadEvents = useServerEventsStore((s) => s.loadEvents);

  const source = useAuditFilterStore((s) => s.source);
  const search = useAuditFilterStore((s) => s.search);
  const page = useAuditFilterStore((s) => s.page);
  const dateRange = useAuditFilterStore((s) => s.dateRange);
  const setSource = useAuditFilterStore((s) => s.setSource);
  const setSearch = useAuditFilterStore((s) => s.setSearch);
  const setPage = useAuditFilterStore((s) => s.setPage);
  const setDateRange = useAuditFilterStore((s) => s.setDateRange);

  const sourceFilters = useMemo(
    () =>
      [
        { value: "all" as const, label: d.filterAll },
        { value: "moderation" as const, label: d.filterModeration },
        { value: "event" as const, label: d.filterServerEvents },
      ] as const,
    [d.filterAll, d.filterModeration, d.filterServerEvents],
  );

  useEffect(() => {
    if (!guildId) return;
    void loadModeration(guildId);
    void loadEvents(guildId);
  }, [guildId, loadModeration, loadEvents]);

  const rows = useMemo<AuditRow[]>(() => {
    const moderation: AuditRow[] = modEntries.map((entry, index) => ({
      id: `mod-${index}-${entry.created_at}`,
      source: "moderation",
      category: "moderation",
      action: entry.action,
      summary: formatDict(d.moderationSummary, {
        moderator: entry.moderator_name,
        action: entry.action,
        target: entry.target,
      }),
      actor: entry.moderator_name,
      created_at: entry.created_at,
      fields: {
        [d.fieldTarget]: entry.target,
        [d.fieldReason]: entry.reason || "—",
        ...(entry.detail ? { [d.fieldDetail]: entry.detail } : {}),
      },
    }));

    const events: AuditRow[] = eventEntries.map((entry) => ({
      id: `evt-${entry.id}`,
      eventId: entry.id,
      source: "event",
      category: entry.category,
      action: entry.action,
      summary: (entry.description || "").replace(/<@!?\d+>/g, "@member"),
      actor: entry.actor_name || "—",
      created_at: entry.created_at,
      fields: entry.fields ?? {},
    }));

    return [...moderation, ...events].sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  }, [modEntries, eventEntries, d]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (source !== "all" && row.source !== source) return false;
      if (!isInDateRange(row.created_at, dateRange)) return false;
      if (!query) return true;
      return [
        row.action,
        row.summary,
        row.category,
        row.actor,
        ...Object.values(row.fields),
      ]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
  }, [rows, source, search, dateRange]);

  if (guildLoading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          {d.loading}
        </div>
      </Card>
    );
  }

  if (guildError || !guildId) {
    return (
      <Card>
        <CAlert color="warning" className="mb-0">
          {guildError ?? d.botOffline}
        </CAlert>
      </Card>
    );
  }

  const loading = modLoading || eventsLoading;

  return (
    <Card>
      <div className="d-flex flex-column gap-3">
        <div className="d-flex flex-wrap align-items-center justify-content-between gap-3">
          <div>
            <h2 className="h5 mb-0 fw-semibold">
              {info?.title ?? dict.featureInfo.auditLogs.title}
            </h2>
            <p className="mt-1 mb-0 small text-body-secondary">
              {info?.description}
            </p>
          </div>

          <div className="d-flex align-items-center gap-2 flex-wrap">
            <CButtonGroup role="group" size="sm">
              {sourceFilters.map((filter) => (
                <Button
                  key={filter.value}
                  variant={source === filter.value ? "primary" : "secondary"}
                  size="sm"
                  onClick={() => setSource(filter.value)}
                >
                  {filter.label}
                </Button>
              ))}
            </CButtonGroup>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                void loadModeration(guildId);
                void loadEvents(guildId);
              }}
            >
              {d.refresh}
            </Button>
          </div>
        </div>

        {loading ? (
          <div className="d-flex align-items-center gap-2 text-body-secondary">
            <CSpinner size="sm" />
            {d.loadingShort}
          </div>
        ) : (
          <DataTable
            columns={[
              {
                key: "source",
                header: d.colSource,
                cell: (row) => (
                  <Badge
                    variant={CATEGORY_VARIANTS[row.category] ?? "neutral"}
                  >
                    {row.source === "moderation"
                      ? d.filterModeration
                      : row.category}
                  </Badge>
                ),
              },
              { key: "action", header: d.colAction, cell: (row) => row.action },
              {
                key: "summary",
                header: d.colDetails,
                cell: (row) => row.summary,
              },
              { key: "actor", header: d.colActor, cell: (row) => row.actor },
              {
                key: "when",
                header: d.colWhen,
                className: "text-nowrap",
                cell: (row) => formatDateTime(row.created_at, lang),
              },
            ]}
            rows={filtered}
            rowKey={(row) => row.id}
            emptyMessage={d.empty}
            search={search}
            onSearchChange={setSearch}
            searchPlaceholder={d.searchPlaceholder}
            page={page}
            pageSize={12}
            onPageChange={setPage}
            expandable={(row) =>
              row.source === "event" && row.eventId && guildId ? (
                <AuditChangeDetails
                  guildId={guildId}
                  eventId={row.eventId}
                  summary={row.summary}
                  actor={row.actor}
                  action={row.action}
                  createdAtLabel={formatDateTime(row.created_at, lang)}
                  fallbackFields={row.fields}
                />
              ) : (
                <div className="d-flex flex-column gap-2">
                  <div>
                    <span className="small fw-semibold text-body-secondary">
                      {d.colDetails}
                    </span>
                    <div className="norgoth-audit-wrap">{row.summary || "—"}</div>
                  </div>
                  {Object.keys(row.fields).length > 0 ? (
                    <dl className="row g-1 mb-0 mt-1 small">
                      {Object.entries(row.fields).map(([label, value]) => (
                        <div className="col-12 d-flex gap-2" key={label}>
                          <dt
                            className="text-body-secondary"
                            style={{ minWidth: 140 }}
                          >
                            {label}
                          </dt>
                          <dd className="mb-0 norgoth-audit-wrap">{value}</dd>
                        </div>
                      ))}
                    </dl>
                  ) : null}
                </div>
              )
            }
            toolbar={
              <div className="d-flex align-items-center gap-2 flex-wrap">
                <CFormSelect
                  size="sm"
                  value={source}
                  onChange={(e) =>
                    setSource(e.target.value as AuditSource | "all")
                  }
                  aria-label={d.filterBySourceAria}
                  style={{ minWidth: 170 }}
                >
                  {sourceFilters.map((filter) => (
                    <option key={filter.value} value={filter.value}>
                      {filter.label}
                    </option>
                  ))}
                </CFormSelect>
                <DateRangePicker value={dateRange} onChange={setDateRange} />
              </div>
            }
          />
        )}
      </div>
    </Card>
  );
}
