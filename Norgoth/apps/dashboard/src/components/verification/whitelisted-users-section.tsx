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
  type WhitelistEntry,
} from "@/stores/verification-lists-store";

const PAGE_SIZE = 8;

export function WhitelistedUsersSection({ guildId }: { guildId: string }) {
  const params = useParams();
  const lang = String(params?.lang || "en");

  const entries = useVerificationListsStore((s) => s.whitelist);
  const loading = useVerificationListsStore((s) => s.whitelistLoading);
  const error = useVerificationListsStore((s) => s.whitelistError);
  const load = useVerificationListsStore((s) => s.loadWhitelist);
  const add = useVerificationListsStore((s) => s.addWhitelist);
  const remove = useVerificationListsStore((s) => s.removeWhitelist);

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [addOpen, setAddOpen] = useState(false);
  const [userId, setUserId] = useState("");
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [pendingRemove, setPendingRemove] = useState<WhitelistEntry | null>(null);
  const [removing, setRemoving] = useState(false);

  useEffect(() => {
    if (guildId) void load(guildId);
  }, [guildId, load]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter(
      (e) =>
        e.discord_user_id.includes(q) ||
        (e.reason ?? "").toLowerCase().includes(q)
    );
  }, [entries, search]);

  const columns: DataTableColumn<WhitelistEntry>[] = [
    {
      key: "id",
      header: "Discord User ID",
      cell: (row) => (
        <span className="font-monospace small">{row.discord_user_id}</span>
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
        <Button variant="danger" size="sm" onClick={() => setPendingRemove(row)}>
          Remove
        </Button>
      ),
    },
  ];

  async function submitAdd() {
    const trimmed = userId.trim();
    if (!/^[0-9]{1,20}$/.test(trimmed)) {
      setFormError("Enter a valid Discord user ID (numeric snowflake).");
      return;
    }
    setSaving(true);
    setFormError(null);
    const result = await add(guildId, trimmed, reason.trim());
    setSaving(false);
    if (!result.ok) {
      setFormError(result.error ?? "Could not add the user.");
      return;
    }
    setUserId("");
    setReason("");
    setAddOpen(false);
  }

  async function confirmRemove() {
    if (!pendingRemove) return;
    setRemoving(true);
    await remove(guildId, pendingRemove.discord_user_id);
    setRemoving(false);
    setPendingRemove(null);
  }

  return (
    <div className="d-flex flex-column gap-3">
      <div className="d-flex align-items-start justify-content-between gap-3 flex-wrap">
        <p className="mb-0 small text-body-secondary" style={{ maxWidth: 520 }}>
          Whitelisted users bypass High Risk Server manual review, alt-account
          (shared IP) detection, and VPN/proxy denial. They cannot bypass core
          integrity checks such as malformed or revoked Discord authorization.
        </p>
        <Button variant="primary" size="sm" onClick={() => setAddOpen(true)}>
          Add User
        </Button>
      </div>

      {error ? (
        <CAlert color="warning" className="mb-0 py-2">
          {error}
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
        searchPlaceholder="Search by user ID or note…"
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        emptyMessage={loading ? "Loading…" : "No whitelisted users configured."}
      />

      <FeatureConfigurationModal
        visible={addOpen}
        onClose={() => setAddOpen(false)}
        title="Whitelist User"
        description="This user will bypass High Risk Server review, shared-IP, and VPN/proxy checks."
        category="community"
        onSave={submitAdd}
        saving={saving}
        error={formError}
        saveLabel="Add User"
      >
        <div className="d-flex flex-column gap-3">
          <div>
            <CFormLabel>Discord User ID</CFormLabel>
            <CFormInput
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
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
              placeholder="Why is this user whitelisted?"
            />
          </div>
        </div>
      </FeatureConfigurationModal>

      <ConfirmDialog
        visible={pendingRemove !== null}
        title="Remove whitelisted user"
        message={
          pendingRemove
            ? `Remove user ${pendingRemove.discord_user_id} from the whitelist?`
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
