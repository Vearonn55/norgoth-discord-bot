"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { CAlert, CSpinner } from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DateRangePicker,
  isInDateRange,
} from "@/components/ui/date-range-filter";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useVerificationStore } from "@/stores/verification-store";
import { formatDateTime } from "@/lib/datetime";

type StatusFilter = "all" | "manual_review" | "success" | "failed";

const STATUS_FILTERS: { id: StatusFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "manual_review", label: "Manual review" },
  { id: "success", label: "Allowed" },
  { id: "failed", label: "Denied" },
];

export function VerificationLogsPanel() {
  const params = useParams();
  const lang = String(params?.lang || "en");
  const { guildId, loading: guildLoading, error: guildError } = useFirstGuild();

  const logs = useVerificationStore((s) => s.logs);
  const loading = useVerificationStore((s) => s.logsLoading);
  const error = useVerificationStore((s) => s.logsError);
  const dateRange = useVerificationStore((s) => s.dateRange);
  const setDateRange = useVerificationStore((s) => s.setDateRange);
  const loadLogs = useVerificationStore((s) => s.loadLogs);

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  useEffect(() => {
    if (!guildId) return;
    void loadLogs(guildId);
  }, [guildId, loadLogs]);

  const filteredLogs = useMemo(
    () =>
      logs.filter(
        (log) =>
          isInDateRange(log.created_at, dateRange) &&
          (statusFilter === "all" || log.status === statusFilter)
      ),
    [logs, dateRange, statusFilter]
  );

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
    <Card>
      <div className="d-flex flex-column gap-3">
        <div className="d-flex align-items-center justify-content-between gap-3">
          <div>
            <h2 className="h5 mb-0 fw-semibold">Verification Log</h2>
            <p className="mt-1 mb-0 small text-body-secondary">
              Read-only history of verification attempts for this server. Use
              Manual Verification to review pending members.
            </p>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => void loadLogs(guildId)}
          >
            Refresh
          </Button>
        </div>

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

        <DateRangePicker value={dateRange} onChange={setDateRange} />

        {loading ? (
          <div className="d-flex align-items-center gap-2 text-body-secondary">
            <CSpinner size="sm" />
            Loading…
          </div>
        ) : error ? (
          <CAlert color="warning" className="mb-0">
            {error}
          </CAlert>
        ) : filteredLogs.length === 0 ? (
          <div className="border rounded px-3 py-4 small text-body-secondary">
            {logs.length === 0
              ? "No verification attempts yet. Open Verification Settings to copy the verification link or publish the Discord verify panel."
              : "No verification attempts in this date range."}
          </div>
        ) : (
          <div className="d-flex flex-column gap-2">
            {filteredLogs.map((log) => (
              <div
                key={log.id}
                className="d-flex flex-column flex-md-row align-items-md-center justify-content-md-between gap-2 border rounded px-3 py-2"
              >
                <div className="d-flex align-items-center gap-2 flex-wrap">
                  <Badge
                    variant={
                      log.status === "success"
                        ? "success"
                        : log.status === "manual_review"
                          ? "warning"
                          : "danger"
                    }
                  >
                    {log.status === "success"
                      ? "Allowed"
                      : log.status === "manual_review"
                        ? "Manual review"
                        : "Denied"}
                  </Badge>
                  <span className="font-monospace small">
                    {log.discord_user_id}
                  </span>
                  {log.reason && (
                    <span className="small text-body-secondary">
                      {log.reason.replaceAll("_", " ")}
                    </span>
                  )}
                </div>

                <div className="d-flex align-items-center gap-2 small text-body-secondary flex-wrap">
                  {log.vpn_or_proxy_detected && (
                    <Badge variant="warning">VPN</Badge>
                  )}
                  {log.shared_ip_detected && (
                    <Badge variant="warning">Shared IP</Badge>
                  )}
                  {log.high_risk_guild_detected && (
                    <Badge variant="warning">High risk server</Badge>
                  )}
                  {log.reviewed_by ? (
                    <span title={`Reviewed by ${log.reviewed_by}`}>
                      reviewed{" "}
                      {log.reviewed_at
                        ? formatDateTime(log.reviewed_at, lang)
                        : ""}
                    </span>
                  ) : null}
                  <span>{formatDateTime(log.created_at, lang)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
