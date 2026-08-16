"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { CAlert, CBadge } from "@coreui/react";
import { formatDateTime } from "@/lib/datetime";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useContentNotificationsStore } from "@/stores/content-notifications-store";
import { useContentNotificationsCopy } from "@/lib/content-notifications-copy";
import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import type { DeliveryHistoryItem } from "@/stores/content-notifications-store";

const PAGE_SIZE = 50;

export function DeliveryHistoryPanel() {
  const copy = useContentNotificationsCopy();
  const params = useParams();
  const lang = String(params?.lang || "en");
  const { guildId } = useFirstGuild();
  const history = useContentNotificationsStore((s) => s.history);
  const historyTotal = useContentNotificationsStore((s) => s.historyTotal);
  const error = useContentNotificationsStore((s) => s.error);
  const loadHistory = useContentNotificationsStore((s) => s.loadHistory);
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (!guildId) return;
    void loadHistory(guildId, {
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    });
  }, [guildId, loadHistory, page]);

  const columns: DataTableColumn<DeliveryHistoryItem>[] = useMemo(
    () => [
      {
        key: "time",
        header: copy.colTime,
        cell: (item) => (
          <span className="small text-body-secondary">
            {formatDateTime(item.created_at, lang)}
          </span>
        ),
      },
      {
        key: "platform",
        header: copy.colPlatform,
        cell: (item) => (
          <span className="text-uppercase small">{item.platform}</span>
        ),
      },
      {
        key: "creator",
        header: copy.colCreator,
        cell: (item) => item.creator_name,
      },
      {
        key: "content",
        header: copy.colContent,
        cell: (item) =>
          item.content_url ? (
            <a href={item.content_url} target="_blank" rel="noreferrer">
              {item.title || item.content_url}
            </a>
          ) : (
            item.title || "—"
          ),
      },
      {
        key: "status",
        header: copy.colStatus,
        cell: (item) => (
          <CBadge
            color={
              item.status === "succeeded"
                ? "success"
                : item.status === "dead"
                  ? "danger"
                  : "warning"
            }
          >
            {item.status}
          </CBadge>
        ),
      },
      {
        key: "latency",
        header: copy.colLatency,
        cell: (item) => (
          <span className="small">
            {item.latency_ms != null ? `${item.latency_ms} ms` : "—"}
          </span>
        ),
      },
    ],
    [copy, lang],
  );

  return (
    <div className="d-flex flex-column gap-3">
      <p className="small text-body-secondary mb-0">{copy.historyIntro}</p>
      {error && history.length === 0 ? (
        <CAlert color="danger" className="py-2 px-3 mb-0">
          {copy.historyError}
        </CAlert>
      ) : null}
      <DataTable
        columns={columns}
        rows={history}
        rowKey={(row) => row.job_id}
        emptyMessage={copy.emptyHistory}
        serverSide
        totalCount={historyTotal}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
      />
    </div>
  );
}
