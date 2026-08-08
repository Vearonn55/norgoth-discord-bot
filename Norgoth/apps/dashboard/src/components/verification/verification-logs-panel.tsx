"use client";

import { useEffect, useMemo } from "react";
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

export function VerificationLogsPanel() {
  const { guildId, loading: guildLoading, error: guildError } = useFirstGuild();

  const logs = useVerificationStore((s) => s.logs);
  const loading = useVerificationStore((s) => s.logsLoading);
  const error = useVerificationStore((s) => s.logsError);
  const dateRange = useVerificationStore((s) => s.dateRange);
  const setDateRange = useVerificationStore((s) => s.setDateRange);
  const loadLogs = useVerificationStore((s) => s.loadLogs);

  useEffect(() => {
    if (!guildId) return;
    void loadLogs(guildId);
  }, [guildId, loadLogs]);

  const filteredLogs = useMemo(
    () => logs.filter((log) => isInDateRange(log.created_at, dateRange)),
    [logs, dateRange]
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
              Latest verification attempts for this server.
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
          <CAlert color="secondary" className="mb-0">
            {logs.length === 0
              ? "No verification attempts yet. Share the verification link from Settings → Guild Configuration."
              : "No verification attempts in this date range."}
          </CAlert>
        ) : (
          <div className="d-flex flex-column gap-2">
            {filteredLogs.map((log) => (
              <div
                key={log.id}
                className="d-flex flex-column flex-md-row align-items-md-center justify-content-md-between gap-2 border rounded px-3 py-2"
              >
                <div className="d-flex align-items-center gap-2 flex-wrap">
                  <Badge
                    variant={log.status === "success" ? "success" : "danger"}
                  >
                    {log.status === "success" ? "Allowed" : "Denied"}
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
                  {log.blacklisted_guild_detected && (
                    <Badge variant="warning">Blacklisted guild</Badge>
                  )}
                  <span>{new Date(log.created_at).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
