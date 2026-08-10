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
import { useFirstGuild } from "@/lib/use-first-guild";
import { create } from "zustand";
import { useModerationLogsStore } from "@/stores/moderation-logs-store";
import { useServerEventsStore } from "@/stores/server-events-store";

type AuditSource = "moderation" | "event";

type AuditRow = {
  id: string;
  source: AuditSource;
  category: string;
  action: string;
  summary: string;
  actor: string;
  created_at: string;
  fields: Record<string, string>;
};

const SOURCE_FILTERS: { value: AuditSource | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "moderation", label: "Moderation" },
  { value: "event", label: "Server Events" },
];

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

// Local UI-only store for the merged view's filters (keeps the two source
// stores focused on their own data).
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
      summary: `${entry.moderator_name} used /${entry.action} on ${entry.target}`,
      actor: entry.moderator_name,
      created_at: entry.created_at,
      fields: {
        Target: entry.target,
        Reason: entry.reason || "—",
        ...(entry.detail ? { Detail: entry.detail } : {}),
      },
    }));

    const events: AuditRow[] = eventEntries.map((entry) => ({
      id: `evt-${entry.id}`,
      source: "event",
      category: entry.category,
      action: entry.action,
      summary: entry.description.replace(/<@!?\d+>/g, "@member"),
      actor: entry.actor_name || entry.fields?.Actor || "—",
      created_at: entry.created_at,
      fields: entry.fields ?? {},
    }));

    return [...moderation, ...events].sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }, [modEntries, eventEntries]);

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
          Loading audit logs…
        </div>
      </Card>
    );
  }

  if (guildError || !guildId) {
    return (
      <Card>
        <CAlert color="warning" className="mb-0">
          {guildError ?? "Bot is offline or not in any server yet."}
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
            <h2 className="h5 mb-0 fw-semibold">Audit</h2>
            <p className="mt-1 mb-0 small text-body-secondary">
              Moderation actions and server events in one timeline.
            </p>
          </div>

          <div className="d-flex align-items-center gap-2 flex-wrap">
            <CButtonGroup role="group" size="sm">
              {SOURCE_FILTERS.map((filter) => (
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
              Refresh
            </Button>
          </div>
        </div>

        {loading ? (
          <div className="d-flex align-items-center gap-2 text-body-secondary">
            <CSpinner size="sm" />
            Loading…
          </div>
        ) : (
          <DataTable
            columns={[
              {
                key: "source",
                header: "Source",
                cell: (row) => (
                  <Badge
                    variant={CATEGORY_VARIANTS[row.category] ?? "neutral"}
                  >
                    {row.source === "moderation" ? "Moderation" : row.category}
                  </Badge>
                ),
              },
              { key: "action", header: "Action", cell: (row) => row.action },
              {
                key: "summary",
                header: "Details",
                cell: (row) => row.summary,
              },
              { key: "actor", header: "Actor", cell: (row) => row.actor },
              {
                key: "when",
                header: "When",
                className: "text-nowrap",
                cell: (row) => formatDateTime(row.created_at, lang),
              },
            ]}
            rows={filtered}
            rowKey={(row) => row.id}
            emptyMessage="No audit events recorded yet."
            search={search}
            onSearchChange={setSearch}
            searchPlaceholder="Search actions, actors, details…"
            page={page}
            pageSize={12}
            onPageChange={setPage}
            expandable={(row) => (
              <div className="d-flex flex-column gap-2">
                <div>
                  <span className="small fw-semibold text-body-secondary">
                    Details
                  </span>
                  <div>{row.summary || "—"}</div>
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
                        <dd className="mb-0">{value}</dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
              </div>
            )}
            toolbar={
              <div className="d-flex align-items-center gap-2 flex-wrap">
                <CFormSelect
                  size="sm"
                  value={source}
                  onChange={(e) =>
                    setSource(e.target.value as AuditSource | "all")
                  }
                  aria-label="Filter by source"
                  style={{ minWidth: 170 }}
                >
                  {SOURCE_FILTERS.map((filter) => (
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
