"use client";

import { useEffect, useMemo, useState } from "react";
import { CAlert, CBadge, CFormSelect, CSpinner } from "@coreui/react";
import { useParams } from "next/navigation";
import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import { Button } from "@/components/ui/button";
import { PlatformAvatar } from "@/components/content-notifications/platform-avatar";
import { AccountEditorModal } from "@/components/content-notifications/account-editor-modal";
import {
  localizeEventType,
  localizeSubscriptionStatus,
  useContentNotificationsCopy,
} from "@/lib/content-notifications-copy";
import {
  CN_FUNCTIONAL_PLATFORMS,
  CN_PAGE_SIZE,
  clampPage,
  withCnPlatform,
  type CnPlatformFilter,
} from "@/lib/cn-url-state";
import { useCnUrlState } from "@/lib/use-cn-url-state";
import { formatDateTime } from "@/lib/datetime";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useGuildStore } from "@/stores/guild-store";
import {
  useContentNotificationsStore,
  type ContentAccount,
} from "@/stores/content-notifications-store";

const PLATFORM_LABELS: Record<string, string> = {
  youtube: "YouTube",
  twitch: "Twitch",
  kick: "Kick",
  x: "X",
  tiktok: "TikTok",
};

export function AccountsPanel() {
  const copy = useContentNotificationsCopy();
  const params = useParams();
  const lang = String(params?.lang || "en");
  const { guildId } = useFirstGuild();
  const { state, patchState, replaceState } = useCnUrlState();
  const resources = useGuildStore((s) => s.resources);
  const accounts = useContentNotificationsStore((s) => s.accounts);
  const accountsTotal = useContentNotificationsStore((s) => s.accountsTotal);
  const platforms = useContentNotificationsStore((s) => s.platforms);
  const workerOnline = useContentNotificationsStore((s) => s.workerOnline);
  const loading = useContentNotificationsStore((s) => s.loading);
  const error = useContentNotificationsStore((s) => s.error);
  const loadAccounts = useContentNotificationsStore((s) => s.loadAccounts);
  const loadTemplates = useContentNotificationsStore((s) => s.loadTemplates);
  const loadStyles = useContentNotificationsStore((s) => s.loadStyles);
  const deleteAccount = useContentNotificationsStore((s) => s.deleteAccount);
  const toggleAccount = useContentNotificationsStore((s) => s.toggleAccount);
  const testNotification = useContentNotificationsStore((s) => s.testNotification);
  const [rowFeedback, setRowFeedback] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);

  const page = clampPage(state.page, hasLoaded ? accountsTotal : state.page * CN_PAGE_SIZE, CN_PAGE_SIZE);

  useEffect(() => {
    if (!guildId) return;
    void loadTemplates(guildId);
    void loadStyles(guildId);
  }, [guildId, loadStyles, loadTemplates]);

  useEffect(() => {
    if (!guildId) return;
    void loadAccounts(guildId, {
      platform: state.platform,
      limit: CN_PAGE_SIZE,
      offset: (page - 1) * CN_PAGE_SIZE,
    }).finally(() => setHasLoaded(true));
  }, [guildId, loadAccounts, page, state.platform]);

  useEffect(() => {
    if (!hasLoaded || loading) return;
    const clamped = clampPage(state.page, accountsTotal, CN_PAGE_SIZE);
    if (clamped !== state.page) patchState({ page: clamped });
  }, [accountsTotal, hasLoaded, loading, patchState, state.page]);

  const channelName = (id: string) =>
    resources?.channels.find((channel) => channel.id === id)?.name ?? id;

  const editingAccount =
    state.panel === "edit"
      ? accounts.find((row) => row.id === state.account) ?? null
      : null;

  const columns: DataTableColumn<ContentAccount>[] = useMemo(
    () => [
      {
        key: "platform",
        header: copy.colPlatform,
        cell: (row) => (
          <span className="text-uppercase small">
            {PLATFORM_LABELS[row.source?.platform ?? ""] ??
              row.source?.platform ??
              "—"}
          </span>
        ),
      },
      {
        key: "identity",
        header: copy.colCreator,
        cell: (row) => {
          const name =
            row.source?.display_name ||
            row.source?.username ||
            copy.unknownCreator;
          return (
            <div className="d-flex align-items-center gap-2">
              <PlatformAvatar
                src={row.source?.avatar_url}
                displayName={name}
                platform={row.source?.platform ?? ""}
              />
              <div className="min-w-0">
                <div className="fw-semibold text-truncate">{name}</div>
                <div className="small text-body-secondary text-uppercase">
                  {localizeSubscriptionStatus(row.status, copy)}
                </div>
              </div>
            </div>
          );
        },
      },
      {
        key: "destination",
        header: copy.colDestination,
        cell: (row) => (
          <span className="small">#{channelName(row.destination_channel_id)}</span>
        ),
      },
      {
        key: "status",
        header: copy.colStatus,
        cell: (row) => (
          <CBadge color={row.enabled ? "success" : "secondary"}>
            {row.enabled ? copy.enabled : copy.paused}
          </CBadge>
        ),
      },
      {
        key: "contentType",
        header: copy.colContentType,
        cell: (row) => (
          <span className="small">
            {(row.event_types ?? [])
              .map((type) => localizeEventType(type, copy))
              .join(", ") || "—"}
          </span>
        ),
      },
      {
        key: "lastEvent",
        header: copy.colLastEvent,
        cell: (row) => (
          <span className="small text-body-secondary">
            {formatDateTime(row.last_event_at, lang)}
          </span>
        ),
      },
      {
        key: "actions",
        header: copy.colActions,
        cell: (row) => (
          <div className="d-flex flex-wrap gap-1">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() =>
                patchState({ panel: "edit", account: row.id })
              }
            >
              {copy.edit}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => {
                if (!guildId) return;
                void toggleAccount(guildId, row.id, !row.enabled).catch((err) =>
                  setRowFeedback(
                    err instanceof Error ? err.message : copy.updateFailed
                  )
                );
              }}
            >
              {row.enabled ? copy.pause : copy.enable}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => {
                if (!guildId) return;
                void testNotification(guildId, row.id)
                  .then(() => setRowFeedback(copy.testQueued))
                  .catch((err) =>
                    setRowFeedback(
                      err instanceof Error ? err.message : copy.testFailed
                    )
                  );
              }}
            >
              {copy.test}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="danger"
              onClick={() => {
                if (!guildId) return;
                void deleteAccount(guildId, row.id);
              }}
            >
              {copy.delete}
            </Button>
          </div>
        ),
      },
    ],
    [
      channelName,
      copy,
      deleteAccount,
      guildId,
      lang,
      patchState,
      testNotification,
      toggleAccount,
    ]
  );

  const emptyMessage =
    state.platform === "all" ? copy.emptyAccounts : copy.noMatchingAccounts;
  const tiktokMeta = platforms.find((p) => p.platform === "tiktok");

  return (
    <div className="d-flex flex-column gap-4">
      <div>
        <p className="mb-0 small text-body-secondary">{copy.accountsIntro}</p>
        <div className="mt-2 d-flex gap-2 flex-wrap">
          {CN_FUNCTIONAL_PLATFORMS.map((id) => {
            const meta = platforms.find((p) => p.platform === id);
            const blocked = meta && !meta.available;
            const activeCount = meta?.active_count ?? 0;
            const activeLimit = meta?.active_limit ?? 0;
            return (
              <CBadge
                key={id}
                color={blocked ? "secondary" : "success"}
                className="text-uppercase"
              >
                {PLATFORM_LABELS[id]}
                {blocked ? ` · ${copy.blocked}` : ""}
                {` · ${activeCount}/${activeLimit}`}
              </CBadge>
            );
          })}
          <CBadge color={workerOnline ? "success" : "warning"}>
            {workerOnline ? copy.workerOnline : copy.workerOffline}
          </CBadge>
        </div>
        {tiktokMeta ? (
          <p className="small text-warning mb-0 mt-2" role="status">
            {copy.tiktokUnsupported}
          </p>
        ) : null}
      </div>

      {rowFeedback ? (
        <p className="small text-body-secondary mb-0">{rowFeedback}</p>
      ) : null}
      {error ? (
        <CAlert color="danger" className="py-2 px-3 mb-0">
          {copy.accountsError}
        </CAlert>
      ) : null}

      {loading ? (
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" /> {copy.loadingAccounts}
        </div>
      ) : null}

      <DataTable
        columns={columns}
        rows={accounts}
        rowKey={(row) => row.id}
        emptyMessage={emptyMessage}
        serverSide
        totalCount={accountsTotal}
        page={page}
        pageSize={CN_PAGE_SIZE}
        onPageChange={(next) => patchState({ page: next })}
        toolbar={
          <div className="d-flex flex-wrap align-items-center gap-2">
            <CFormSelect
              aria-label={copy.platform}
              value={state.platform}
              style={{ maxWidth: 220 }}
              onChange={(e) =>
                replaceState(
                  withCnPlatform(state, e.target.value as CnPlatformFilter)
                )
              }
            >
              <option value="all">{copy.allPlatforms}</option>
              {CN_FUNCTIONAL_PLATFORMS.map((id) => (
                <option key={id} value={id}>
                  {PLATFORM_LABELS[id]}
                </option>
              ))}
            </CFormSelect>
            <Button
              type="button"
              onClick={() => patchState({ panel: "add", account: null })}
            >
              {copy.addAccount}
            </Button>
          </div>
        }
      />

      {guildId ? (
        <AccountEditorModal
          guildId={guildId}
          mode={state.panel === "edit" ? "edit" : "add"}
          account={editingAccount}
          visible={
            state.panel === "add" ||
            (state.panel === "edit" && Boolean(editingAccount))
          }
          onClose={() => patchState({ panel: null, account: null })}
        />
      ) : null}
    </div>
  );
}
