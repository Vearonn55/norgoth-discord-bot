"use client";

import { useEffect } from "react";
import { CSpinner } from "@coreui/react";
import { Badge } from "@/components/ui/badge";
import {
  auditFieldLabel,
  auditPermissionLabel,
  formatAuditValue,
} from "@/lib/audit-permissions";
import { useLocaleDict } from "@/lib/locale-dict";
import {
  useServerEventsStore,
  type AuditOverwriteChange,
  type EventLogDetail,
} from "@/stores/server-events-store";

type AuditChangeDetailsProps = {
  guildId: string;
  eventId: string;
  summary: string;
  actor: string;
  action: string;
  createdAtLabel: string;
  fallbackFields?: Record<string, string>;
};

function StateBadge({
  state,
}: {
  state: "allow" | "deny" | "inherit" | "granted" | "revoked" | "added" | "removed";
}) {
  const d = useLocaleDict().auditLogsPage;
  const labels = {
    allow: d.stateAllow,
    deny: d.stateDeny,
    inherit: d.stateInherit,
    granted: d.stateGranted,
    revoked: d.stateRevoked,
    added: d.stateAdded,
    removed: d.stateRemoved,
  };
  const variants = {
    allow: "success",
    deny: "danger",
    inherit: "neutral",
    granted: "success",
    revoked: "danger",
    added: "info",
    removed: "warning",
  } as const;
  return <Badge variant={variants[state]}>{labels[state]}</Badge>;
}

function groupOverwrites(items: AuditOverwriteChange[]): Map<string, AuditOverwriteChange[]> {
  const groups = new Map<string, AuditOverwriteChange[]>();
  for (const item of items) {
    const key = `${item.target_kind}:${item.target_id}`;
    const list = groups.get(key) ?? [];
    list.push(item);
    groups.set(key, list);
  }
  return groups;
}

function PermissionSection({ detail }: { detail: EventLogDetail }) {
  const dict = useLocaleDict();
  const d = dict.auditLogsPage;
  const perms = detail.detail?.permission_changes;
  if (!perms) {
    return null;
  }

  if (perms.kind === "role_bits") {
    const granted = perms.granted ?? [];
    const revoked = perms.revoked ?? [];
    if (granted.length === 0 && revoked.length === 0) {
      return null;
    }
    return (
      <div className="d-flex flex-column gap-2">
        <div className="small fw-semibold">{d.permissions}</div>
        {granted.length > 0 ? (
          <div className="d-flex flex-column gap-1">
            <div className="d-flex align-items-center gap-2">
              <StateBadge state="granted" />
              <span className="small">{d.stateGranted}</span>
            </div>
            <ul className="mb-0 ps-3 norgoth-audit-wrap">
              {granted.map((item) => (
                <li key={`g-${item.permission}-${item.unknown_mask ?? ""}`}>
                  {auditPermissionLabel(dict, item.permission, item.unknown_mask)}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {revoked.length > 0 ? (
          <div className="d-flex flex-column gap-1">
            <div className="d-flex align-items-center gap-2">
              <StateBadge state="revoked" />
              <span className="small">{d.stateRevoked}</span>
            </div>
            <ul className="mb-0 ps-3 norgoth-audit-wrap">
              {revoked.map((item) => (
                <li key={`r-${item.permission}-${item.unknown_mask ?? ""}`}>
                  {auditPermissionLabel(dict, item.permission, item.unknown_mask)}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    );
  }

  const items = perms.items ?? [];
  if (items.length === 0 && !perms.category_synced) {
    return null;
  }
  const groups = groupOverwrites(items);
  return (
    <div className="d-flex flex-column gap-2">
      <div className="small fw-semibold">{d.permissions}</div>
      {perms.category_synced ? (
        <div className="small text-body-secondary">{d.categorySynced}</div>
      ) : null}
      {Array.from(groups.entries()).map(([key, group]) => {
        const first = group[0];
        const added = group.every((item) => item.change === "overwrite_added");
        const removed = group.every((item) => item.change === "overwrite_removed");
        return (
          <div key={key} className="d-flex flex-column gap-1 norgoth-audit-wrap">
            <div className="d-flex flex-wrap align-items-center gap-2">
              <span className="fw-semibold">
                {first.target_name} ({first.target_kind} {first.target_id})
              </span>
              {added ? <StateBadge state="added" /> : null}
              {removed ? <StateBadge state="removed" /> : null}
              {added ? <span className="small">{d.overwriteAdded}</span> : null}
              {removed ? <span className="small">{d.overwriteRemoved}</span> : null}
            </div>
            <ul className="mb-0 ps-3">
              {group.map((item) => (
                <li
                  key={`${item.permission}-${item.previous}-${item.next}-${item.change}`}
                  className="d-flex flex-wrap align-items-center gap-2 py-1"
                >
                  <span>
                    {auditPermissionLabel(dict, item.permission, item.unknown_mask)}
                  </span>
                  <StateBadge
                    state={
                      item.previous === "allow" || item.previous === "deny" || item.previous === "inherit"
                        ? item.previous
                        : "inherit"
                    }
                  />
                  <span aria-hidden="true">→</span>
                  <StateBadge
                    state={
                      item.next === "allow" || item.next === "deny" || item.next === "inherit"
                        ? item.next
                        : "inherit"
                    }
                  />
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

export function AuditChangeDetails({
  guildId,
  eventId,
  summary,
  actor,
  action,
  createdAtLabel,
  fallbackFields,
}: AuditChangeDetailsProps) {
  const dict = useLocaleDict();
  const d = dict.auditLogsPage;
  const detail = useServerEventsStore((state) => state.details[eventId]);
  const loading = useServerEventsStore((state) => state.detailLoading[eventId]);
  const error = useServerEventsStore((state) => state.detailError[eventId]);
  const loadEventDetail = useServerEventsStore((state) => state.loadEventDetail);

  useEffect(() => {
    void loadEventDetail(guildId, eventId);
  }, [guildId, eventId, loadEventDetail]);

  const identity = (
    <dl className="row g-1 mb-0 small">
      <div className="col-12 d-flex gap-2">
        <dt className="text-body-secondary" style={{ minWidth: 140 }}>
          {d.colAction}
        </dt>
        <dd className="mb-0 norgoth-audit-wrap">{action}</dd>
      </div>
      <div className="col-12 d-flex gap-2">
        <dt className="text-body-secondary" style={{ minWidth: 140 }}>
          {d.colActor}
        </dt>
        <dd className="mb-0 norgoth-audit-wrap">{actor}</dd>
      </div>
      <div className="col-12 d-flex gap-2">
        <dt className="text-body-secondary" style={{ minWidth: 140 }}>
          {d.colWhen}
        </dt>
        <dd className="mb-0">{createdAtLabel}</dd>
      </div>
      {detail?.event_type ? (
        <div className="col-12 d-flex gap-2">
          <dt className="text-body-secondary" style={{ minWidth: 140 }}>
            {d.eventType}
          </dt>
          <dd className="mb-0 norgoth-audit-wrap">{detail.event_type}</dd>
        </div>
      ) : null}
      {detail?.target?.name || detail?.target?.id ? (
        <div className="col-12 d-flex gap-2">
          <dt className="text-body-secondary" style={{ minWidth: 140 }}>
            {d.fieldTarget}
          </dt>
          <dd className="mb-0 norgoth-audit-wrap">
            {[detail.target?.kind, detail.target?.name].filter(Boolean).join(" ")}
            {detail.target?.id ? ` (${d.targetId} ${detail.target.id})` : ""}
          </dd>
        </div>
      ) : null}
      {detail?.source ? (
        <div className="col-12 d-flex gap-2">
          <dt className="text-body-secondary" style={{ minWidth: 140 }}>
            {d.eventSource}
          </dt>
          <dd className="mb-0">{detail.source}</dd>
        </div>
      ) : null}
      {detail?.reason ? (
        <div className="col-12 d-flex gap-2">
          <dt className="text-body-secondary" style={{ minWidth: 140 }}>
            {d.fieldReason}
          </dt>
          <dd className="mb-0 norgoth-audit-wrap">{detail.reason}</dd>
        </div>
      ) : null}
      {detail?.correlation_id ? (
        <div className="col-12 d-flex gap-2">
          <dt className="text-body-secondary" style={{ minWidth: 140 }}>
            {d.correlationId}
          </dt>
          <dd className="mb-0 norgoth-audit-wrap">{detail.correlation_id}</dd>
        </div>
      ) : null}
      <div className="col-12 d-flex gap-2">
        <dt className="text-body-secondary" style={{ minWidth: 140 }}>
          {d.colDetails}
        </dt>
        <dd className="mb-0 norgoth-audit-wrap">{summary || "—"}</dd>
      </div>
    </dl>
  );

  if (loading && !detail) {
    return (
      <div className="d-flex flex-column gap-2 norgoth-audit-changes">
        {identity}
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          {d.loadingShort}
        </div>
      </div>
    );
  }

  if (error && !detail) {
    return (
      <div className="d-flex flex-column gap-2 norgoth-audit-changes">
        {identity}
        <div className="small text-danger">{d.detailError}</div>
      </div>
    );
  }

  const fieldChanges = detail?.detail?.field_changes ?? [];
  const hasPerms = Boolean(
    detail?.detail?.permission_changes &&
      ((detail.detail.permission_changes.kind === "role_bits" &&
        ((detail.detail.permission_changes.granted?.length ?? 0) > 0 ||
          (detail.detail.permission_changes.revoked?.length ?? 0) > 0)) ||
        (detail.detail.permission_changes.kind === "overwrites" &&
          (detail.detail.permission_changes.items?.length ?? 0) > 0)),
  );
  const legacy = detail?.legacy !== false && fieldChanges.length === 0 && !hasPerms;

  return (
    <div className="d-flex flex-column gap-3 norgoth-audit-changes">
      {identity}
      {legacy ? (
        <div className="small text-body-secondary">{d.legacyDetail}</div>
      ) : (
        <div className="d-flex flex-column gap-2">
          <div className="small fw-semibold">{d.changes}</div>
          {fieldChanges.length === 0 && !hasPerms ? (
            <div className="small text-body-secondary">{d.detailEmpty}</div>
          ) : null}
          {fieldChanges.length > 0 ? (
            <div className="table-responsive">
              <table className="table table-sm table-borderless mb-0 small">
                <thead>
                  <tr>
                    <th scope="col">{d.colAction}</th>
                    <th scope="col">{d.fieldPrevious}</th>
                    <th scope="col">{d.fieldNew}</th>
                  </tr>
                </thead>
                <tbody>
                  {fieldChanges.map((change) => (
                    <tr key={change.field}>
                      <td className="text-body-secondary">
                        {auditFieldLabel(dict, change.field)}
                      </td>
                      <td className="norgoth-audit-wrap">
                        {formatAuditValue(change.previous)}
                      </td>
                      <td className="norgoth-audit-wrap">
                        {formatAuditValue(change.next)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {detail ? <PermissionSection detail={detail} /> : null}
          {detail?.detail?.truncated ? (
            <div className="small text-body-secondary">{d.truncated}</div>
          ) : null}
        </div>
      )}
      {legacy && fallbackFields && Object.keys(fallbackFields).length > 0 ? (
        <dl className="row g-1 mb-0 small">
          {Object.entries(fallbackFields).map(([label, value]) => (
            <div className="col-12 d-flex gap-2" key={label}>
              <dt className="text-body-secondary" style={{ minWidth: 140 }}>
                {label}
              </dt>
              <dd className="mb-0 norgoth-audit-wrap">{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}
