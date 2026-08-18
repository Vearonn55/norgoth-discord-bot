"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  CFormCheck,
  CFormInput,
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
import { ChannelSelect } from "@/components/ui/channel-select";
import { ChannelPickerToolbar } from "@/components/ui/refresh-channels-button";
import { EmbedDraftCreator } from "@/components/embed-messages/embed-draft-creator";
import { useFirstGuild } from "@/lib/use-first-guild";
import { formatDateTime } from "@/lib/datetime";
import {
  useEmbedMessagesStore,
  type EmbedMessage,
  type EmbedSyncStatus,
} from "@/stores/embed-messages-store";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";

const PAGE_SIZE = 10;

const DEPLOY_ERROR_KEYS = [
  "permission_missing",
  "unknown_channel",
  "invalid_payload",
  "rate_limited",
  "timeout",
  "bot_missing",
  "deploy_in_progress",
  "content_too_long_for_delivery",
  "embed_total_exceeded",
] as const;

const RESYNC_ERROR_KEYS = [
  "already_synced",
  "message_missing",
  "resync_message_count_mismatch",
  "resync_in_progress",
  "permission_missing",
  "unknown_channel",
  "invalid_payload",
  "rate_limited",
  "timeout",
  "bot_missing",
] as const;

function deployErrorCopy(
  d: Record<string, unknown>,
  code: string | null,
  fallback: string
): string {
  if (!code) return fallback;
  if (!(DEPLOY_ERROR_KEYS as readonly string[]).includes(code)) return fallback;
  const localized = d[code];
  return typeof localized === "string" && localized ? localized : fallback;
}

function resyncErrorCopy(
  d: Record<string, unknown>,
  code: string | null,
  fallback: string
): string {
  if (!code) return fallback;
  if (!(RESYNC_ERROR_KEYS as readonly string[]).includes(code)) return fallback;
  const localized = d[code];
  return typeof localized === "string" && localized ? localized : fallback;
}

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
  labels,
}: {
  status: EmbedSyncStatus;
  synced: number;
  deployments: number;
  labels: {
    statusSynced: string;
    statusOutOfDate: string;
    statusNeedsRepair: string;
    statusMissing: string;
    statusError: string;
    statusDraftOnly: string;
  };
}): { variant: BadgeVariant; label: string } {
  switch (status) {
    case "synced":
      return {
        variant: "success",
        label: formatDict(labels.statusSynced, {
          synced,
          total: deployments,
        }),
      };
    case "out_of_date":
      return {
        variant: "warning",
        label: formatDict(labels.statusOutOfDate, {
          synced,
          total: deployments,
        }),
      };
    case "needs_feature_repair":
      return { variant: "warning", label: labels.statusNeedsRepair };
    case "missing":
      return {
        variant: "warning",
        label: formatDict(labels.statusMissing, {
          synced,
          total: deployments,
        }),
      };
    case "error":
      return {
        variant: "danger",
        label: formatDict(labels.statusError, {
          synced,
          total: deployments,
        }),
      };
    case "pending":
      return { variant: "warning", label: labels.statusDraftOnly };
    case "draft_only":
    default:
      return { variant: "neutral", label: labels.statusDraftOnly };
  }
}

export function EmbedMessagesPanel({ lang }: Props) {
  const dict = useLocaleDict();
  const d = dict.embedLibraryPage;
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
        setFeedback(formatDict(d.deployedFeedback, { name: deployFor.name }));
        setFeedbackError(false);
        setDeployFor(null);
        setDeployChannelId("");
      } else {
        const state = useEmbedMessagesStore.getState();
        setFeedback(
          deployErrorCopy(
            d as unknown as Record<string, unknown>,
            state.errorCode,
            state.error ?? d.deployFailed
          )
        );
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
          formatDict(d.resyncFeedback, {
            name: message.name,
            synced: result.synced_count,
            total: result.deployment_count,
          })
        );
        setFeedbackError(false);
      } else {
        const state = useEmbedMessagesStore.getState();
        setFeedback(
          resyncErrorCopy(
            d as unknown as Record<string, unknown>,
            state.errorCode,
            state.error ?? d.resyncFailed
          )
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
          formatDict(d.reconcileFeedback, {
            name: message.name,
            synced: result.synced_count,
            total: result.deployment_count,
          })
        );
        setFeedbackError(false);
      } else {
        setFeedback(
          useEmbedMessagesStore.getState().error ?? d.reconcileFailed
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
            d.stillUsed
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
            placeholder={d.searchPlaceholder}
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
            {d.newEmbed}
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
            {d.empty}
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
                labels: d,
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
                        ? d.notDeployed
                        : formatDict(
                            deployments === 1 ? d.usedInOne : d.usedInMany,
                            { count: deployments },
                          )}{" "}
                      · {formatDict(d.updated, {
                        time: formatDateTime(message.updated_at, lang),
                      })}
                    </div>
                  </div>
                  <div className="d-flex flex-wrap align-items-center gap-2 flex-shrink-0">
                    <Badge variant={statusBadge.variant}>
                      {statusBadge.label}
                    </Badge>
                    {!isDraftOnly && needsResync ? (
                      <Badge variant="warning">{d.editedNeedsResync}</Badge>
                    ) : null}
                    <Button variant="secondary" size="sm" asChild>
                      <Link
                        href={`/${lang}/messages/embed-messages/${message.id}`}
                      >
                        {d.edit}
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
                      {d.deploy}
                    </Button>
                    {!isDraftOnly ? (
                      <>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => void handleResync(message)}
                          disabled={busy}
                          title={d.resyncTitle}
                        >
                          {busy ? d.working : d.reSync}
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => void handleReconcile(message)}
                          disabled={busy}
                        >
                          {d.check}
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
                      aria-label={d.deleteAria}
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
              {d.previous}
            </Button>
            <span className="small text-body-secondary">
              {formatDict(d.pageOf, { current: currentPage, total: totalPages })}
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
            >
              {d.next}
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
          <CModalTitle>{d.newEmbed}</CModalTitle>
        </CModalHeader>
        <CModalBody className="norgoth-embed-create-modal-body">
          {createOpen ? (
            <EmbedDraftCreator
              key={createKey}
              guildId={guildId}
              channels={channels}
              mode="create"
              compact
              createLabel={d.saveDraft}
              cancelLabel={d.cancel}
              onCancel={() => setCreateOpen(false)}
              onCreated={(created) => {
                setCreateOpen(false);
                setFeedback(formatDict(d.createdFeedback, { name: created.name }));
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
          <CModalTitle>{formatDict(d.deployTitle, { name: deployFor?.name ?? "" })}</CModalTitle>
        </CModalHeader>
        <CModalBody>
          <p className="small text-body-secondary">
            {d.deployDesc}
          </p>
          <ChannelPickerToolbar label={d.selectChannel} />
          <ChannelSelect
            channels={channels}
            value={deployChannelId}
            onChange={setDeployChannelId}
            emptyLabel={d.selectChannel}
          />
        </CModalBody>
        <CModalFooter>
          <Button variant="secondary" onClick={() => setDeployFor(null)}>
            {d.cancel}
          </Button>
          <Button
            variant="primary"
            onClick={() => void handleDeploy()}
            disabled={deploying || !deployChannelId}
          >
            {deploying ? d.deploying : d.deploy}
          </Button>
        </CModalFooter>
      </CModal>

      <ConfirmDialog
        visible={pendingDelete !== null}
        title={d.deleteTitle}
        message={
          <div className="d-flex flex-column gap-3">
            <p className="mb-0 text-body-secondary">
              {formatDict(d.deleteMessage, {
                name: pendingDelete?.name ?? "",
              })}
            </p>
            <CFormCheck
              id="delete-discord-messages"
              label={d.deleteDiscordAlso}
              checked={deleteDiscord}
              onChange={(e) => setDeleteDiscord(e.target.checked)}
            />
          </div>
        }
        confirmLabel={d.deleteConfirm}
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
