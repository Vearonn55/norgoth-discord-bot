"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { CBadge } from "@coreui/react";
import { formatDateTime } from "@/lib/datetime";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useContentNotificationsStore } from "@/stores/content-notifications-store";

export function DeliveryHistoryPanel() {
  const params = useParams();
  const lang = String(params?.lang || "en");
  const { guildId } = useFirstGuild();
  const history = useContentNotificationsStore((s) => s.history);
  const loadHistory = useContentNotificationsStore((s) => s.loadHistory);

  useEffect(() => {
    if (guildId) void loadHistory(guildId);
  }, [guildId, loadHistory]);

  return (
    <div className="d-flex flex-column gap-3">
      <p className="small text-body-secondary mb-0">
        Delivery attempts for this server. Duplicates are suppressed by platform
        content identity.
      </p>
      <div className="table-responsive">
        <table className="table table-sm align-middle mb-0">
          <thead>
            <tr>
              <th>Time</th>
              <th>Platform</th>
              <th>Creator</th>
              <th>Content</th>
              <th>Status</th>
              <th>Latency</th>
            </tr>
          </thead>
          <tbody>
            {history.map((item) => (
              <tr key={item.job_id}>
                <td className="small text-body-secondary">
                  {formatDateTime(item.created_at, lang)}
                </td>
                <td className="text-uppercase small">{item.platform}</td>
                <td>{item.creator_name}</td>
                <td className="small">
                  {item.content_url ? (
                    <a href={item.content_url} target="_blank" rel="noreferrer">
                      {item.title || item.content_url}
                    </a>
                  ) : (
                    item.title || "—"
                  )}
                </td>
                <td>
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
                </td>
                <td className="small">
                  {item.latency_ms != null ? `${item.latency_ms} ms` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {history.length === 0 ? (
        <p className="text-body-secondary mb-0">No delivery history yet.</p>
      ) : null}
    </div>
  );
}
