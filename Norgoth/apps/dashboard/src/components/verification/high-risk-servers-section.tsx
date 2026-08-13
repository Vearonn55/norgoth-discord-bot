"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { CAlert, CFormInput, CFormLabel, CFormTextarea } from "@coreui/react";
import { Button } from "@/components/ui/button";
import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { formatDateTime } from "@/lib/datetime";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";
import {
  useVerificationListsStore,
  type HighRiskGuildEntry,
} from "@/stores/verification-lists-store";

const PAGE_SIZE = 8;

export function HighRiskServersSection({ guildId }: { guildId: string }) {
  const dict = useLocaleDict();
  const d = dict.verificationPage;
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
      header: d.colServerId,
      cell: (row) => (
        <span className="font-monospace small">
          {row.high_risk_discord_guild_id}
        </span>
      ),
    },
    {
      key: "reason",
      header: d.colNote,
      cell: (row) => (
        <span className="small text-body-secondary">{row.reason || "—"}</span>
      ),
    },
    {
      key: "created",
      header: d.colAdded,
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
          {d.remove}
        </Button>
      ),
    },
  ];

  async function submitAdd() {
    const trimmed = targetId.trim();
    if (!/^[0-9]{1,20}$/.test(trimmed)) {
      setFormError(d.invalidServerId);
      return;
    }
    setSaving(true);
    setFormError(null);
    const result = await add(guildId, trimmed, reason.trim());
    setSaving(false);
    if (!result.ok) {
      setFormError(result.error ?? d.couldNotAddServer);
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
          {d.highRiskIntro}
        </p>
        <Button variant="primary" size="sm" onClick={() => setAddOpen(true)}>
          {d.addServer}
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
            {loading ? d.retrying : d.retry}
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
        searchPlaceholder={d.searchHighRisk}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        emptyMessage={
          error
            ? d.emptyHighRiskError
            : loading
              ? d.loading
              : d.emptyHighRisk
        }
      />

      <FeatureConfigurationModal
        visible={addOpen}
        onClose={() => setAddOpen(false)}
        title={d.addHighRiskTitle}
        description={d.addHighRiskDesc}
        category="community"
        onSave={submitAdd}
        saving={saving}
        error={formError}
        saveLabel={d.addServer}
      >
        <div className="d-flex flex-column gap-3">
          <div>
            <CFormLabel>{d.colServerId}</CFormLabel>
            <CFormInput
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              placeholder="123456789012345678"
              inputMode="numeric"
            />
          </div>
          <div>
            <CFormLabel>{d.noteOptional}</CFormLabel>
            <CFormTextarea
              rows={2}
              value={reason}
              maxLength={200}
              onChange={(e) => setReason(e.target.value)}
              placeholder={d.highRiskNotePlaceholder}
            />
          </div>
        </div>
      </FeatureConfigurationModal>

      <ConfirmDialog
        visible={pendingRemove !== null}
        title={d.removeHighRiskTitle}
        message={
          pendingRemove
            ? formatDict(d.removeHighRiskMessage, {
                id: pendingRemove.high_risk_discord_guild_id,
              })
            : ""
        }
        confirmLabel={d.remove}
        destructive
        busy={removing}
        onConfirm={confirmRemove}
        onCancel={() => setPendingRemove(null)}
      />
    </div>
  );
}
