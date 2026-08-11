"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { CAlert, CFormInput, CFormLabel, CFormTextarea } from "@coreui/react";
import { Button } from "@/components/ui/button";
import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { formatDateTime } from "@/lib/datetime";
import {
  useVerificationListsStore,
  type HighRiskGuildEntry,
} from "@/stores/verification-lists-store";

const PAGE_SIZE = 8;

export function HighRiskServersSection({ guildId }: { guildId: string }) {
  const params = useParams();
  const lang = String(params?.lang || "en");

  const entries = useVerificationListsStore((s) => s.highRisk);
  const loading = useVerificationListsStore((s) => s.highRiskLoading);
  const error = useVerificationListsStore((s) => s.highRiskError);
  const load = useVerificationListsStore((s) => s.loadHighRisk);
  const add = useVerificationListsStore((s) => s.addHighRisk);
  const remove = useVerificationListsStore((s) => s.removeHighRisk);

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [addOpen, setAddOpen] = useState(false);
  const [targetId, setTargetId] = useState("");
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [pendingRemove, setPendingRemove] = useState<HighRiskGuildEntry | null>(
    null
  );
  const [removing, setRemoving] = useState(false);

  useEffect(() => {
    if (guildId) void load(guildId);
  }, [guildId, load]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter(
      (e) =>
        e.high_risk_discord_guild_id.includes(q) ||
        (e.reason ?? "").toLowerCase().includes(q)
    );
  }, [entries, search]);

  const columns: DataTableColumn<HighRiskGuildEntry>[] = [
    {
      key: "id",
      header: "Discord Server ID",
      cell: (row) => (
        <span className="font-monospace small">
          {row.high_risk_discord_guild_id}
        </span>
      ),
    },
    {
      key: "reason",
      header: "Note",
      cell: (row) => (
        <span className="small text-body-secondary">{row.reason || "—"}</span>
      ),
    },
    {
      key: "created",
      header: "Added",
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
        <Button
          variant="danger"
          size="sm"
          onClick={() => setPendingRemove(row)}
        >
          Remove
        </Button>
      ),
    },
  ];

  async function submitAdd() {
    const trimmed = targetId.trim();
    if (!/^[0-9]{1,20}$/.test(trimmed)) {
      setFormError("Enter a valid Discord server ID (numeric snowflake).");
      return;
    }
    setSaving(true);
    setFormError(null);
    const result = await add(guildId, trimmed, reason.trim());
    setSaving(false);
    if (!result.ok) {
      setFormError(result.error ?? "Could not add the server.");
      return;
    }
    setTargetId("");
    setReason("");
    setAddOpen(false);
  }

  async function confirmRemove() {
    if (!pendingRemove) return;
    setRemoving(true);
    await remove(guildId, pendingRemove.high_risk_discord_guild_id);
    setRemoving(false);
    setPendingRemove(null);
  }

  return (
    <div className="d-flex flex-column gap-3">
      <div className="d-flex align-items-start justify-content-between gap-3 flex-wrap">
        <p className="mb-0 small text-body-secondary" style={{ maxWidth: 520 }}>
          If a verifying member belongs to any of these Discord servers, their
          verification is routed to Manual Review instead of being auto-approved
          (unless a stronger deny rule applies or the user is whitelisted).
        </p>
        <Button variant="primary" size="sm" onClick={() => setAddOpen(true)}>
          Add Server
        </Button>
      </div>

      {error ? (
        <CAlert
          color="danger"
          className="mb-0 py-2 d-flex align-items-center justify-content-between gap-3"
        >
          <span>{error}</span>
          <Button
            variant="danger"
            size="sm"
            onClick={() => void load(guildId)}
            disabled={loading}
          >
            {loading ? "Retrying…" : "Retry"}
          </Button>
        </CAlert>
      ) : null}

      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(row) => row.id}
        search={search}
        onSearchChange={(value) => {
          setSearch(value);
          setPage(1);
        }}
        searchPlaceholder="Search by server ID or note…"
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        emptyMessage={
          error
            ? "Could not load high-risk servers."
            : loading
              ? "Loading…"
              : "No high-risk servers configured."
        }
      />

      <FeatureConfigurationModal
        visible={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add High Risk Server"
        description="Members of this server will be routed to Manual Review during verification."
        category="community"
        onSave={submitAdd}
        saving={saving}
        error={formError}
        saveLabel="Add Server"
      >
        <div className="d-flex flex-column gap-3">
          <div>
            <CFormLabel>Discord Server ID</CFormLabel>
            <CFormInput
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              placeholder="123456789012345678"
              inputMode="numeric"
            />
          </div>
          <div>
            <CFormLabel>Note (optional)</CFormLabel>
            <CFormTextarea
              rows={2}
              value={reason}
              maxLength={200}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Why is this server high-risk?"
            />
          </div>
        </div>
      </FeatureConfigurationModal>

      <ConfirmDialog
        visible={pendingRemove !== null}
        title="Remove high-risk server"
        message={
          pendingRemove
            ? `Remove server ${pendingRemove.high_risk_discord_guild_id} from the high-risk list?`
            : ""
        }
        confirmLabel="Remove"
        destructive
        busy={removing}
        onConfirm={confirmRemove}
        onCancel={() => setPendingRemove(null)}
      />
    </div>
  );
}
