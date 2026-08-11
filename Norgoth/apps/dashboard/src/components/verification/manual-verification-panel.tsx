"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CAlert, CSpinner } from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import { ManualReviewModal } from "@/components/verification/manual-review-modal";
import { useFirstGuild } from "@/lib/use-first-guild";
import { formatDateTime } from "@/lib/datetime";
import {
  deriveManualReviewReasons,
  manualReviewReasonShortLabel,
} from "@/lib/verification/manual-review-reasons";
import {
  useManualReviewStore,
  type ManualReviewItem,
  type ManualReviewStatusFilter,
} from "@/stores/manual-review-store";

const STATUS_FILTERS: { id: ManualReviewStatusFilter; label: string }[] = [
  { id: "manual_review", label: "Pending review" },
  { id: "success", label: "Approved" },
  { id: "failed", label: "Denied" },
  { id: "all", label: "All" },
];

function memberName(item: ManualReviewItem): string {
  return (
    item.display_name ||
    item.username ||
    (item.discord_user_id.length >= 4
      ? `User ${item.discord_user_id.slice(-4)}`
      : `User ${item.discord_user_id}`)
  );
}

export function ManualVerificationPanel() {
  const params = useParams();
  const lang = String(params?.lang || "en");
  const { guildId, loading: guildLoading, error: guildError } = useFirstGuild();

  const items = useManualReviewStore((s) => s.items);
  const total = useManualReviewStore((s) => s.total);
  const page = useManualReviewStore((s) => s.page);
  const pageSize = useManualReviewStore((s) => s.pageSize);
  const query = useManualReviewStore((s) => s.query);
  const statusFilter = useManualReviewStore((s) => s.statusFilter);
  const loading = useManualReviewStore((s) => s.loading);
  const error = useManualReviewStore((s) => s.error);
  const setPage = useManualReviewStore((s) => s.setPage);
  const setQuery = useManualReviewStore((s) => s.setQuery);
  const setStatusFilter = useManualReviewStore((s) => s.setStatusFilter);
  const load = useManualReviewStore((s) => s.load);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  // Debounced reload whenever the guild, page, search, or status changes.
  useEffect(() => {
    if (!guildId) return;
    const handle = window.setTimeout(() => void load(guildId), 250);
    return () => window.clearTimeout(handle);
  }, [guildId, page, query, statusFilter, load]);

  function openReview(item: ManualReviewItem) {
    setSelectedId(item.id);
    setModalOpen(true);
  }

  const columns: DataTableColumn<ManualReviewItem>[] = [
    {
      key: "member",
      header: "Member",
      cell: (row) => (
        <div className="d-flex align-items-center gap-2">
          {row.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={row.avatar_url}
              alt=""
              width={28}
              height={28}
              className="rounded-circle flex-shrink-0"
              style={{ objectFit: "cover" }}
            />
          ) : null}
          <div className="min-w-0">
            <div className="text-truncate">{memberName(row)}</div>
            <div className="font-monospace text-body-secondary" style={{ fontSize: 11 }}>
              {row.discord_user_id}
            </div>
          </div>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (row) =>
        row.status === "success" ? (
          <Badge variant="success">Allowed</Badge>
        ) : row.status === "manual_review" ? (
          <Badge variant="warning">Pending</Badge>
        ) : (
          <Badge variant="danger">Denied</Badge>
        ),
    },
    {
      key: "triggers",
      header: "Triggers",
      cell: (row) => {
        const codes = deriveManualReviewReasons(row);
        if (codes.length === 0) {
          return <span className="small text-body-secondary">—</span>;
        }
        return (
          <div className="d-flex flex-wrap gap-1">
            {codes.map((code) => (
              <Badge key={code} variant="warning">
                {manualReviewReasonShortLabel(code, lang)}
              </Badge>
            ))}
          </div>
        );
      },
    },
    {
      key: "created",
      header: "Attempted",
      cell: (row) => (
        <span className="small text-body-secondary">
          {formatDateTime(row.created_at, lang)}
        </span>
      ),
    },
    {
      key: "actions",
      header: "",
      className: "text-end",
      cell: (row) => (
        <Button variant="secondary" size="sm" onClick={() => openReview(row)}>
          Review
        </Button>
      ),
    },
  ];

  if (guildLoading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          Loading…
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

  return (
    <>
      <Card>
        <div className="d-flex flex-column gap-3">
          <div className="d-flex flex-wrap align-items-center gap-2">
            {STATUS_FILTERS.map((filter) => (
              <Button
                key={filter.id}
                variant={statusFilter === filter.id ? "primary" : "secondary"}
                size="sm"
                onClick={() => setStatusFilter(filter.id)}
              >
                {filter.label}
              </Button>
            ))}
          </div>

          {error ? (
            <CAlert color="warning" className="mb-0">
              {error}
            </CAlert>
          ) : loading && items.length === 0 ? (
            <div className="d-flex align-items-center gap-2 text-body-secondary">
              <CSpinner size="sm" />
              Loading…
            </div>
          ) : (
            <DataTable
              columns={columns}
              rows={items}
              rowKey={(row) => row.id}
              serverSide
              totalCount={total}
              page={page}
              pageSize={pageSize}
              onPageChange={setPage}
              search={query}
              onSearchChange={setQuery}
              searchPlaceholder="Search by username or user ID…"
              emptyMessage={
                statusFilter === "manual_review"
                  ? "No members are awaiting review. You're all caught up."
                  : "No verification attempts match these filters."
              }
            />
          )}
        </div>
      </Card>

      <ManualReviewModal
        visible={modalOpen}
        guildId={guildId}
        attemptId={selectedId}
        lang={lang}
        onClose={() => setModalOpen(false)}
        onReviewed={() => void load(guildId)}
      />
    </>
  );
}
