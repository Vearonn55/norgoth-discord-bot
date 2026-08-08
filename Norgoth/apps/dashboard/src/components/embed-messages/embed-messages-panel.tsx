"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { CFormCheck, CFormInput, CSpinner } from "@coreui/react";
import { cilTrash } from "@coreui/icons";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { useFirstGuild } from "@/lib/use-first-guild";
import {
  useEmbedMessagesStore,
  type EmbedMessage,
} from "@/stores/embed-messages-store";

const PAGE_SIZE = 10;

type Props = {
  lang: string;
};

export function EmbedMessagesPanel({ lang }: Props) {
  const { guildId } = useFirstGuild();
  const messages = useEmbedMessagesStore((s) => s.messages);
  const loading = useEmbedMessagesStore((s) => s.loading);
  const load = useEmbedMessagesStore((s) => s.load);
  const remove = useEmbedMessagesStore((s) => s.remove);
  const publish = useEmbedMessagesStore((s) => s.publish);
  const resync = useEmbedMessagesStore((s) => s.resync);
  const reconcile = useEmbedMessagesStore((s) => s.reconcile);

  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pendingDelete, setPendingDelete] = useState<EmbedMessage | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteDiscord, setDeleteDiscord] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState(false);

  async function handlePublish(message: EmbedMessage) {
    if (!guildId) return;
    setBusyId(message.id);
    setFeedback(null);
    try {
      const result = await publish(guildId, message.id);
      if (result) {
        setFeedback(`Published “${message.name}” to its target channels.`);
        setFeedbackError(false);
      } else {
        setFeedback(
          useEmbedMessagesStore.getState().error ?? "Publish failed."
        );
        setFeedbackError(true);
      }
    } finally {
      setBusyId(null);
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
          `Re-synced “${message.name}” (${result.synced_count}/${result.target_count} live).`
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
          `Checked “${message.name}” — ${result.synced_count}/${result.target_count} live in Discord.`
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
      const ok = await remove(guildId, pendingDelete.id, deleteDiscord);
      if (ok) {
        setPendingDelete(null);
        setDeleteDiscord(false);
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
          <Button variant="primary" asChild>
            <Link href={`/${lang}/messages/embed-messages/new`}>
              New Embed Message
            </Link>
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
            No saved embed messages yet.
          </p>
        ) : (
          <div className="d-flex flex-column gap-2">
            {pageItems.map((message) => {
              const targets = message.target_count;
              const synced = message.synced_count;
              const published = message.has_published;
              const needsResync = message.needs_resync;
              const busy = busyId === message.id;
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
                      {targets} target{targets === 1 ? "" : "s"} · Updated{" "}
                      {message.updated_at
                        ? new Date(message.updated_at).toLocaleString()
                        : "—"}
                    </div>
                  </div>
                  <div className="d-flex flex-wrap align-items-center gap-2 flex-shrink-0">
                    {published ? (
                      <Badge variant={synced === targets ? "success" : "warning"}>
                        {synced}/{targets} live
                      </Badge>
                    ) : (
                      <Badge variant="neutral">Draft</Badge>
                    )}
                    {needsResync ? (
                      <Badge variant="warning">Edited — needs re-sync</Badge>
                    ) : null}
                    <Button variant="secondary" size="sm" asChild>
                      <Link
                        href={`/${lang}/messages/embed-messages/${message.id}`}
                      >
                        Edit
                      </Link>
                    </Button>
                    {published ? (
                      <>
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => void handleResync(message)}
                          disabled={busy || targets === 0}
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
                    ) : (
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => void handlePublish(message)}
                        disabled={busy || targets === 0}
                      >
                        {busy ? "Working…" : "Publish"}
                      </Button>
                    )}
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => {
                        setDeleteDiscord(false);
                        setPendingDelete(message);
                      }}
                      aria-label="Delete embed message"
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

      <ConfirmDialog
        visible={pendingDelete !== null}
        title="Delete Template?"
        message={
          <div className="d-flex flex-column gap-3">
            <p className="mb-0 text-body-secondary">
              This removes the reusable embed{" "}
              <strong>{pendingDelete?.name}</strong>. By default, previously
              sent Discord messages are left in place.
            </p>
            <CFormCheck
              id="delete-discord-messages"
              label="Also delete the messages already posted to Discord"
              checked={deleteDiscord}
              onChange={(e) => setDeleteDiscord(e.target.checked)}
            />
          </div>
        }
        confirmLabel="Delete Template"
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
