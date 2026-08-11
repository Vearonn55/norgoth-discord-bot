"use client";

import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/datetime";
import {
  deriveManualReviewReasons,
  manualReviewReasonHeading,
  manualReviewReasonLabel,
} from "@/lib/verification/manual-review-reasons";
import type { ManualReviewDetail, ManualReviewItem } from "@/stores/manual-review-store";

function statusBadge(status: ManualReviewItem["status"]) {
  if (status === "success") return <Badge variant="success">Allowed</Badge>;
  if (status === "manual_review")
    return <Badge variant="warning">Manual review</Badge>;
  return <Badge variant="danger">Denied</Badge>;
}

function displayName(item: ManualReviewItem): string {
  return (
    item.display_name ||
    item.username ||
    (item.discord_user_id.length >= 4
      ? `User ${item.discord_user_id.slice(-4)}`
      : `User ${item.discord_user_id}`)
  );
}

/**
 * Read-only presentation of a verification attempt / manual review record.
 * Shared by the review modal body and the standalone transcript page so both
 * surfaces stay in lockstep. Renders identity, risk analysis, the explicit
 * high-risk-server trigger, and the review outcome. Never shows IP data.
 */
export function ReviewRecord({
  detail,
  lang,
}: {
  detail: ManualReviewDetail;
  lang: string;
}) {
  const name = displayName(detail);
  const initial = name.trim().charAt(0).toUpperCase() || "?";

  const reasonCodes = deriveManualReviewReasons(detail);
  const hasRiskSignals = reasonCodes.length > 0;

  return (
    <div className="d-flex flex-column gap-4">
      <div className="d-flex align-items-center gap-3">
        {detail.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={detail.avatar_url}
            alt=""
            width={48}
            height={48}
            className="rounded-circle flex-shrink-0"
            style={{ objectFit: "cover" }}
          />
        ) : (
          <div
            aria-hidden="true"
            className="d-flex align-items-center justify-content-center rounded-circle border fw-semibold flex-shrink-0"
            style={{ width: 48, height: 48 }}
          >
            {initial}
          </div>
        )}
        <div className="min-w-0">
          <div className="d-flex align-items-center gap-2 flex-wrap">
            <span className="fw-semibold">{name}</span>
            {statusBadge(detail.status)}
          </div>
          {detail.username ? (
            <div className="small text-body-secondary">@{detail.username}</div>
          ) : null}
          <div className="font-monospace small text-body-secondary">
            {detail.discord_user_id}
          </div>
        </div>
      </div>

      {hasRiskSignals ? (
        <div>
          <div className="small fw-semibold text-uppercase text-body-secondary mb-2">
            {manualReviewReasonHeading(lang)}
          </div>
          <ul className="mb-0 ps-3">
            {reasonCodes.map((code) => (
              <li key={code} className="small">
                {manualReviewReasonLabel(code, lang)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div>
        <div className="small fw-semibold text-uppercase text-body-secondary mb-2">
          Risk analysis
        </div>
        {hasRiskSignals ? (
          <div className="d-flex flex-wrap gap-2">
            {detail.vpn_or_proxy_detected ? (
              <Badge variant="warning">VPN / Proxy</Badge>
            ) : null}
            {detail.shared_ip_detected ? (
              <Badge variant="warning">Shared IP</Badge>
            ) : null}
            {detail.high_risk_guild_detected ? (
              <Badge variant="warning">High Risk Server member</Badge>
            ) : null}
          </div>
        ) : (
          <div className="small text-body-secondary">
            No risk signals were recorded for this attempt.
          </div>
        )}
        {detail.reason ? (
          <div className="small text-body-secondary mt-2">
            Decision reason:{" "}
            <span className="fw-medium">
              {detail.reason.replaceAll("_", " ")}
            </span>
          </div>
        ) : null}
      </div>

      {detail.high_risk_guild_detected ? (
        <div>
          <div className="small fw-semibold text-uppercase text-body-secondary mb-2">
            Matched High Risk Servers
          </div>
          {detail.matched_high_risk_servers.length > 0 ? (
            <div className="d-flex flex-column gap-2">
              {detail.matched_high_risk_servers.map((server) => (
                <div
                  key={server.discord_guild_id}
                  className="border rounded px-3 py-2"
                >
                  <div className="font-monospace small">
                    {server.discord_guild_id}
                  </div>
                  {server.reason ? (
                    <div className="small text-body-secondary">
                      {server.reason}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <div className="small text-body-secondary">
              This member belongs to a configured High Risk Server.
            </div>
          )}
        </div>
      ) : null}

      <div className="border-top pt-3 small text-body-secondary">
        <div>Attempted: {formatDateTime(detail.created_at, lang)}</div>
        {detail.reviewed_by ? (
          <div>
            Reviewed by <span className="font-monospace">{detail.reviewed_by}</span>
            {detail.reviewed_at
              ? ` · ${formatDateTime(detail.reviewed_at, lang)}`
              : ""}
          </div>
        ) : (
          <div>Awaiting review.</div>
        )}
      </div>
    </div>
  );
}
