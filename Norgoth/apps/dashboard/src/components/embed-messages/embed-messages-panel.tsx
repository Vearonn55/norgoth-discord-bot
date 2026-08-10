"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  CFormCheck,
  CFormInput,
  CFormSelect,
  CModal,
  CModalBody,
  CModalFooter,
  CModalHeader,
  CModalTitle,
  CSpinner,
} from "@coreui/react";
import { cilTrash } from "@coreui/icons";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { EmbedDraftCreator } from "@/components/embed-messages/embed-draft-creator";
import { useFirstGuild } from "@/lib/use-first-guild";
import { formatDateTime } from "@/lib/datetime";
import {
  useEmbedMessagesStore,
  type EmbedMessage,
  type EmbedSyncStatus,
} from "@/stores/embed-messages-store";

const PAGE_SIZE = 10;

type Props = {
  lang: string;
};

type BadgeVariant = "success" | "warning" | "danger" | "neutral";

/**
 * Map the backend deployment-driven `sync_status` to a badge. A draft with no
 * deployments is "Draft only"; live-but-stale copies show "Out of date"; SAR /
 * feature-owned missing messages show "Needs feature repair".
 */
function statusBadgeFor({
  status,
  synced,
  deployments,
}: {
  status: EmbedSyncStatus;
  synced: number;
  deployments: number;
}): { variant: BadgeVariant; label: string } {
  switch (status) {
    case "synced":
      return { variant: "success", label: `${synced}/${deployments} synced` };
    case "out_of_date":
      return {
        variant: "warning",
        label: `Out of date · ${synced}/${deployments} synced`,
      };
    case "needs_feature_repair":
      return { variant: "warning", label: "Needs feature repair" };
    case "missing":
      return { variant: "warning", label: `Missing · ${synced}/${deployments}` };
    case "error":
      return { variant: "danger", label: `Error · ${synced}/${deployments}` };
    case "draft_only":
    default:
      return { variant: "neutral", label: "Draft only" };
  }
}

export function EmbedMessagesPanel({ lang }: Props) {
  const { guildId, resources } = useFirstGuild();
  const messages = useEmbedMessagesStore((s) => s.messages);
  const loading = useEmbedMessagesStore((s) => s.loading);
  const load = useEmbedMessagesStore((s) => s.load);
  const remove = useEmbedMessagesStore((s) => s.remove);
  const deploy = useEmbedMessagesStore((s) => s.deploy);
  const resync = useEmbedMessagesStore((s) => s.resync);
  const reconcile = useEmbedMessagesStore((s) => s.reconcile);

  const channels = resources?.channels ?? [];

  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pendingDelete, setPendingDelete] = useState<EmbedMessage | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteDiscord, setDeleteDiscord] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  // Bumped on each open so the shared creator remounts with fresh, empty state.
  const [createKey, setCreateKey] = useState(0);
  const [deployFor, setDeployFor] = useState<EmbedMessage | null>(null);
  const [deployChannelId, setDeployChannelId] = useState("");
  const [deploying, setDeploying] = useState(false);

  async function handleDeploy() {
    if (!guildId || !deployFor || !deployChannelId) return;
    setDeploying(true);
    setFeedback(null);
    try {
      const result = await deploy(guildId, deployFor.id, deployChannelId);
      if (result) {
        setFeedback(`Deployed “${deployFor.name}” to the selected channel.`);
        setFeedbackError(false);
        setDeployFor(null);
        setDeployChannelId("");
      } else {
        setFeedback(useEmbedMessagesStore.getState().error ?? "Deploy failed.");
        setFeedbackError(true);
      }
    } finally {
      setDeploying(false);
    }
  }

  async function handleResync(message: EmbedMessage) {
    if (!guildId) return;
    setBusyId(message.id);
    setFeedback(null);
    try {
      const result = await resync(guildId, message.id);
      if (result) {
        setFeedback(
          `Re-synced “${message.name}” (${result.synced_count}/${result.deployment_count} synced).`
        );
        setFeedbackError(false);
      } else {
        setFeedback(
          useEmbedMessagesStore.getState().error ?? "Re-sync failed."
        );
        setFeedbackError(true);
      }
    } finally {
      setBusyId(null);
    }
  }

  async function handleReconcile(message: EmbedMessage) {
    if (!guildId) return;
    setBusyId(message.id);
    setFeedback(null);
    try {
      const result = await reconcile(guildId, message.id);
      if (result) {
        setFeedback(
          `Checked “${message.name}” — ${result.synced_count}/${result.deployment_count} synced in Discord.`
        );
        setFeedbackError(false);
      } else {
        setFeedback(
          useEmbedMessagesStore.getState().error ?? "Status check failed."
        );
        setFeedbackError(true);
      }
    } finally {
      setBusyId(null);
    }
  }

  useEffect(() => {
    if (guildId) void load(guildId);
  }, [guildId, load]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return messages;
    return messages.filter(
      (m) =>
        m.name.toLowerCase().includes(q) ||
        m.description.toLowerCase().includes(q)
    );
  }, [messages, query]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageItems = filtered.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  );

  async function confirmDelete() {
    if (!guildId || !pendingDelete) return;
    setDeleting(true);
    try {
      const ok = await remove(guildId, pendingDelete.id, {
        deleteDiscordMessages: deleteDiscord,
      });
      if (ok) {
        setPendingDelete(null);
        setDeleteDiscord(false);
      } else {
        setFeedback(
          useEmbedMessagesStore.getState().error ??
            "This draft is still used by other features."
        );
        setFeedbackError(true);
        setPendingDelete(null);
      }
    } finally {
      setDeleting(false);
    }
  }

  if (loading && messages.length === 0) {
    return (
      <div className="d-flex justify-content-center py-5">
        <CSpinner />
      </div>
    );
  }

  return (
    <Card>
      <div className="d-flex flex-column gap-3">
        <div className="d-flex flex-wrap align-items-center justify-content-between gap-3">
          <CFormInput
            value={query}
            placeholder="Search embeds…"
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
            style={{ maxWidth: 280 }}
          />
          <Button
            variant="primary"
            onClick={() => {
              setCreateKey((k) => k + 1);
              setCreateOpen(true);
            }}
          >
            New Embed
          </Button>
        </div>

        {feedback ? (
          <div
            className={`small ${feedbackError ? "text-danger" : "text-success"}`}
          >
            {feedback}
          </div>
        ) : null}

        {filtered.length === 0 ? (
          <p className="text-body-secondary small mb-0">
            No saved embed drafts yet.
          </p>
        ) : (
          <div className="d-flex flex-column gap-2">
            {pageItems.map((message) => {
              const deployments = message.deployment_count;
              const synced = message.synced_count;
              const needsResync = message.needs_resync;
              const status = message.sync_status;
              const isDraftOnly = deployments === 0;
              const busy = busyId === message.id;
              const statusBadge = statusBadgeFor({
                status,
                synced,
                deployments,
              });
              return (
                <div
                  key={message.id}
                  className="d-flex flex-column flex-lg-row align-items-lg-center justify-content-between gap-3 border rounded p-3"
                >
                  <div className="overflow-hidden">
                    <div className="fw-semibold text-truncate">
                      {message.name}
                    </div>
                    <div className="small text-body-secondary text-truncate">
                      {message.description || "—"}
                    </div>
                    <div className="small text-body-tertiary">
                      {isDraftOnly
                        ? "Not deployed"
                        : `Used in ${deployments} deployment${
                            deployments === 1 ? "" : "s"
                          }`}{" "}
                      · Updated {formatDateTime(message.updated_at, lang)}
                    </div>
                  </div>
                  <div className="d-flex flex-wrap align-items-center gap-2 flex-shrink-0">
                    <Badge variant={statusBadge.variant}>
                      {statusBadge.label}
                    </Badge>
                    {!isDraftOnly && needsResync ? (
                      <Badge variant="warning">Edited — needs re-sync</Badge>
                    ) : null}
                    <Button variant="secondary" size="sm" asChild>
                      <Link
                        href={`/${lang}/messages/embed-messages/${message.id}`}
                      >
                        Edit
                      </Link>
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => {
                        setDeployChannelId("");
                        setDeployFor(message);
                      }}
                      disabled={busy}
                    >
                      Deploy
                    </Button>
                    {!isDraftOnly ? (
                      <>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => void handleResync(message)}
                          disabled={busy}
                          title="Synchronize the latest content across deployments"
                        >
                          {busy ? "Working…" : "Re-Sync"}
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => void handleReconcile(message)}
                          disabled={busy}
                        >
                          Check
                        </Button>
                      </>
                    ) : null}
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => {
                        setDeleteDiscord(false);
                        setPendingDelete(message);
                      }}
                      aria-label="Delete embed draft"
                    >
                      <Icon icon={cilTrash} />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {totalPages > 1 ? (
          <div className="d-flex align-items-center justify-content-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              Previous
            </Button>
            <span className="small text-body-secondary">
              Page {currentPage} / {totalPages}
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
            >
              Next
            </Button>
          </div>
        ) : null}
      </div>

      <CModal
        visible={createOpen}
        onClose={() => setCreateOpen(false)}
        size="xl"
        alignment="center"
        backdrop
        className="norgoth-embed-create-modal"
      >
        <CModalHeader>
          <CModalTitle>New Embed</CModalTitle>
        </CModalHeader>
        <CModalBody className="norgoth-embed-create-modal-body">
          {createOpen ? (
            <EmbedDraftCreator
              key={createKey}
              guildId={guildId}
              channels={channels}
              mode="create"
              compact
              createLabel="Save Draft"
              cancelLabel="Cancel"
              onCancel={() => setCreateOpen(false)}
              onCreated={(created) => {
                setCreateOpen(false);
                setFeedback(`Created “${created.name}”.`);
                setFeedbackError(false);
              }}
            />
          ) : null}
        </CModalBody>
      </CModal>

      <CModal
        visible={deployFor !== null}
        onClose={() => setDeployFor(null)}
        alignment="center"
        backdrop
      >
        <CModalHeader>
          <CModalTitle>Deploy “{deployFor?.name}”</CModalTitle>
        </CModalHeader>
        <CModalBody>
          <p className="small text-body-secondary">
            Choose a channel to post this embed to now. This creates a tracked
            deployment you can keep in sync from the library.
          </p>
          <CFormSelect
            value={deployChannelId}
            onChange={(e) => setDeployChannelId(e.target.value)}
          >
            <option value="">Select a channel…</option>
            {channels.map((channel) => (
              <option key={channel.id} value={channel.id}>
                #{channel.name}
              </option>
            ))}
          </CFormSelect>
        </CModalBody>
        <CModalFooter>
          <Button variant="secondary" onClick={() => setDeployFor(null)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={() => void handleDeploy()}
            disabled={deploying || !deployChannelId}
          >
            {deploying ? "Deploying…" : "Deploy"}
          </Button>
        </CModalFooter>
      </CModal>

      <ConfirmDialog
        visible={pendingDelete !== null}
        title="Delete Draft?"
        message={
          <div className="d-flex flex-column gap-3">
            <p className="mb-0 text-body-secondary">
              This removes the reusable embed{" "}
              <strong>{pendingDelete?.name}</strong>. By default, previously
              deployed Discord messages are left in place.
            </p>
            <CFormCheck
              id="delete-discord-messages"
              label="Also delete the messages already posted to Discord"
              checked={deleteDiscord}
              onChange={(e) => setDeleteDiscord(e.target.checked)}
            />
          </div>
        }
        confirmLabel="Delete Draft"
        destructive
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => {
          setPendingDelete(null);
          setDeleteDiscord(false);
        }}
      />
    </Card>
  );
}
