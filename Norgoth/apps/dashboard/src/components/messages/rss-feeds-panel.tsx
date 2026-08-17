"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  CAlert,
  CFormCheck,
  CFormInput,
  CFormLabel,
  CFormSelect,
  CSpinner,
} from "@coreui/react";
import { SectionCard } from "@/components/ui/section-card";
import { ChannelSelect } from "@/components/ui/channel-select";
import {
  ChannelPickerToolbar,
  RolePickerToolbar,
} from "@/components/ui/refresh-channels-button";
import { RoleSelect } from "@/components/ui/role-select";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { PageHeader } from "@/components/layout/page-header";
import { ManagingGuildLabel } from "@/components/layout/managing-guild-label";
import { useFirstGuild } from "@/stores/guild-store";
import {
  useRssFeedsStore,
  type RssFeed,
  type RssProbeResult,
} from "@/stores/rss-feeds-store";
import { useModulesStore } from "@/stores/modules-store";
import { Icon } from "@/components/ui/icon";
import { cilNotes } from "@coreui/icons";
import { useFeatureInfo } from "@/lib/feature-info";
import { formatDateTime } from "@/lib/datetime";
import { useLocaleDict, formatDict } from "@/lib/locale-dict";
import { rssErrorMessage } from "@/lib/rss-errors";
import { MutedSection } from "@/components/ui/feature-muting";

type Draft = {
  feed_url: string;
  channel_id: string;
  mention_role_id: string;
  display_name: string;
  poll_interval_seconds: number;
  enabled: boolean;
};

const emptyDraft = (): Draft => ({
  feed_url: "",
  channel_id: "",
  mention_role_id: "",
  display_name: "",
  poll_interval_seconds: 300,
  enabled: true,
});

export function RssFeedsPanel() {
  const params = useParams();
  const lang = String(params?.lang || "en");
  const dict = useLocaleDict();
  const d = dict.rssFeedsPage;
  const { guildId, resources, loading: guildLoading } = useFirstGuild();
  const feeds = useRssFeedsStore((s) => s.feeds);
  const maxFeeds = useRssFeedsStore((s) => s.maxFeeds);
  const workerOnline = useRssFeedsStore((s) => s.workerOnline);
  const loading = useRssFeedsStore((s) => s.loading);
  const saving = useRssFeedsStore((s) => s.saving);
  const error = useRssFeedsStore((s) => s.error);
  const load = useRssFeedsStore((s) => s.load);
  const create = useRssFeedsStore((s) => s.create);
  const update = useRssFeedsStore((s) => s.update);
  const remove = useRssFeedsStore((s) => s.remove);
  const probe = useRssFeedsStore((s) => s.probe);
  const info = useFeatureInfo("rssFeeds");
  const modules = useModulesStore((s) => s.modules);
  const modulesLoading = useModulesStore((s) => s.loading);
  const pendingKey = useModulesStore((s) => s.pendingKey);
  const loadModules = useModulesStore((s) => s.load);
  const toggleModule = useModulesStore((s) => s.toggleModule);

  const rssModuleEnabled =
    modules.find((module) => module.key === "rss_feeds")?.enabled ?? true;

  const intervalOptions = useMemo(
    () => [
      { value: 300, label: d.interval5m },
      { value: 600, label: d.interval10m },
      { value: 900, label: d.interval15m },
      { value: 1800, label: d.interval30m },
      { value: 3600, label: d.interval1h },
    ],
    [d],
  );

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [probeResult, setProbeResult] = useState<RssProbeResult | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
    void loadModules(guildId);
  }, [guildId, load, loadModules]);

  function openCreate() {
    setEditingId(null);
    setDraft(emptyDraft());
    setProbeResult(null);
    setLocalError(null);
    setShowForm(true);
  }

  function openEdit(feed: RssFeed) {
    setEditingId(feed.id);
    setDraft({
      feed_url: feed.feed_url,
      channel_id: feed.channel_id,
      mention_role_id: feed.mention_role_id ?? "",
      display_name: feed.display_name ?? "",
      poll_interval_seconds: feed.poll_interval_seconds,
      enabled: feed.enabled,
    });
    setProbeResult(null);
    setLocalError(null);
    setShowForm(true);
  }

  async function runProbe() {
    if (!guildId || !draft.feed_url.trim()) return;
    setLocalError(null);
    try {
      const result = await probe(guildId, draft.feed_url.trim());
      setProbeResult(result);
      if (result.ok && result.feed_title && !draft.display_name) {
        setDraft((prev) => ({
          ...prev,
          display_name: result.feed_title || "",
        }));
      }
    } catch (e) {
      const code =
        e && typeof e === "object" && "code" in e
          ? String((e as { code?: string }).code ?? "")
          : null;
      setLocalError(
        rssErrorMessage(
          d,
          code,
          e instanceof Error ? e.message : d.probeFailed,
        ),
      );
    }
  }

  async function save() {
    if (!guildId) return;
    setLocalError(null);
    if (!draft.feed_url.trim() || !draft.channel_id) {
      setLocalError(d.urlAndChannelRequired);
      return;
    }
    try {
      if (editingId) {
        await update(guildId, editingId, {
          feed_url: draft.feed_url.trim(),
          channel_id: draft.channel_id,
          mention_role_id: draft.mention_role_id || null,
          clear_mention_role: !draft.mention_role_id,
          display_name: draft.display_name.trim() || null,
          poll_interval_seconds: draft.poll_interval_seconds,
          enabled: draft.enabled,
        });
      } else {
        await create(guildId, {
          feed_url: draft.feed_url.trim(),
          channel_id: draft.channel_id,
          mention_role_id: draft.mention_role_id || null,
          display_name: draft.display_name.trim() || null,
          poll_interval_seconds: draft.poll_interval_seconds,
          enabled: draft.enabled,
        });
      }
      setShowForm(false);
      setEditingId(null);
    } catch (e) {
      const code =
        e && typeof e === "object" && "code" in e
          ? String((e as { code?: string }).code ?? "")
          : null;
      setLocalError(
        rssErrorMessage(
          d,
          code,
          e instanceof Error ? e.message : d.saveFailed,
        ),
      );
    }
  }

  if (guildLoading || loading) {
    return (
      <div className="d-flex align-items-center gap-2">
        <CSpinner size="sm" /> {d.loading}
      </div>
    );
  }

  if (!guildId) {
    return <p className="text-body-secondary">{d.selectServer}</p>;
  }

  const channelName = (id: string) =>
    resources?.channels?.find((c) => c.id === id)?.name ?? id;

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={info?.title ?? "RSS Feeds"}
        category="messages"
        icon={<Icon icon={cilNotes} size="xl" />}
        description={<ManagingGuildLabel />}
        infoKey="rssFeeds"
        masterToggle={{
          enabled: rssModuleEnabled,
          loading:
            modulesLoading || pendingKey === "rss_feeds" || !guildId,
          label: info?.title ?? "RSS Feeds",
          showLabel: false,
          onChange: (checked) => {
            if (!guildId) return;
            void toggleModule(guildId, "rss_feeds", checked);
          },
        }}
      />

      <CAlert color="info" className="mb-0">
        {formatDict(d.infoBanner, { max: maxFeeds })}
      </CAlert>

      {(error || localError) && (
        <p className="text-danger mb-0">{localError || error}</p>
      )}

      <p className="small text-body-secondary mb-0">
        {d.worker}{" "}
        {workerOnline ? d.workerOnline : d.workerOffline} · {feeds.length}/
        {maxFeeds} {d.feedsCount}
      </p>

      <MutedSection enabled={rssModuleEnabled} className="d-flex flex-column gap-4">
      {showForm ? (
        <SectionCard
          level="primary"
          category="messages"
          header={editingId ? d.editFeed : d.newFeed}
        >
          <div className="d-flex flex-column gap-3 p-1">
            <div>
              <CFormLabel>{d.feedUrl}</CFormLabel>
              <div className="d-flex gap-2 flex-wrap">
                <CFormInput
                  value={draft.feed_url}
                  onChange={(e) =>
                    setDraft((prev) => ({ ...prev, feed_url: e.target.value }))
                  }
                  placeholder="https://example.com/feed.xml"
                  className="flex-grow-1"
                />
                <Button variant="secondary" onClick={() => void runProbe()}>
                  {d.probe}
                </Button>
              </div>
              {probeResult ? (
                <p
                  className={`small mt-2 mb-0 ${
                    probeResult.ok ? "text-success" : "text-danger"
                  }`}
                >
                  {probeResult.ok
                    ? `${probeResult.format_hint} · ${probeResult.feed_title ?? "—"} · ${probeResult.item_count} items`
                    : rssErrorMessage(
                        d,
                        probeResult.error_code,
                        probeResult.error,
                      )}
                </p>
              ) : null}
              {probeResult?.ok && probeResult.item_count === 0 ? (
                <p className="small text-body-secondary mt-2 mb-0">
                  {d.emptyFeedWarning}
                </p>
              ) : null}
            </div>
            <div>
              <CFormLabel>{d.displayName}</CFormLabel>
              <CFormInput
                value={draft.display_name}
                onChange={(e) =>
                  setDraft((prev) => ({
                    ...prev,
                    display_name: e.target.value,
                  }))
                }
                placeholder={d.optional}
              />
            </div>
            <div>
              <ChannelPickerToolbar label={d.destinationChannel} />
              <ChannelSelect
                channels={resources?.channels ?? []}
                value={draft.channel_id}
                onChange={(id) =>
                  setDraft((prev) => ({ ...prev, channel_id: id }))
                }
              />
            </div>
            <div>
              <RolePickerToolbar label={d.mentionRole} />
              <RoleSelect
                roles={resources?.roles ?? []}
                value={draft.mention_role_id}
                onChange={(id) =>
                  setDraft((prev) => ({ ...prev, mention_role_id: id }))
                }
                emptyLabel={d.noRole}
              />
            </div>
            <div style={{ maxWidth: 280 }}>
              <CFormLabel>{d.pollInterval}</CFormLabel>
              <CFormSelect
                value={String(draft.poll_interval_seconds)}
                onChange={(e) =>
                  setDraft((prev) => ({
                    ...prev,
                    poll_interval_seconds: Number(e.target.value),
                  }))
                }
              >
                {intervalOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </CFormSelect>
            </div>
            <CFormCheck
              id="rss-enabled"
              label={d.enabled}
              checked={draft.enabled}
              onChange={(e) =>
                setDraft((prev) => ({ ...prev, enabled: e.target.checked }))
              }
            />
            <div className="d-flex gap-2">
              <Button
                variant="primary"
                disabled={saving}
                onClick={() => void save()}
              >
                {saving ? d.saving : d.save}
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setShowForm(false);
                  setEditingId(null);
                }}
              >
                {d.cancel}
              </Button>
            </div>
          </div>
        </SectionCard>
      ) : null}

      <SectionCard level="secondary" category="messages" header={d.feedsHeader}>
        {feeds.length === 0 ? (
          <p className="text-body-secondary mb-0 p-1">{d.empty}</p>
        ) : (
          <div className="table-responsive">
            <table className="table table-dark table-sm align-middle mb-0">
              <thead>
                <tr>
                  <th>{d.colNameUrl}</th>
                  <th>{d.colChannel}</th>
                  <th>{d.colStatus}</th>
                  <th>{d.colLastSuccess}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {feeds.map((feed) => (
                  <tr key={feed.id}>
                    <td>
                      <div className="fw-semibold">
                        {feed.display_name ||
                          feed.format_hint ||
                          d.feedFallback}
                      </div>
                      <div
                        className="small text-body-secondary text-truncate"
                        style={{ maxWidth: 280 }}
                      >
                        {feed.feed_url}
                      </div>
                      {feed.last_error ? (
                        <div className="small text-danger">
                          {feed.last_error}
                        </div>
                      ) : null}
                    </td>
                    <td>#{channelName(feed.channel_id)}</td>
                    <td>
                      <div className="d-flex align-items-center gap-2">
                        <Switch
                          checked={feed.enabled}
                          disabled={saving}
                          onChange={(checked) =>
                            void update(guildId, feed.id, { enabled: checked })
                          }
                          aria-label={`Toggle ${feed.display_name || feed.feed_url}`}
                        />
                        <span className="small">
                          {feed.enabled ? d.on : d.off}
                        </span>
                      </div>
                    </td>
                    <td className="small">
                      {feed.last_success_at
                        ? formatDateTime(feed.last_success_at, lang)
                        : "—"}
                    </td>
                    <td className="text-end">
                      <div className="d-flex gap-2 justify-content-end">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => openEdit(feed)}
                        >
                          {d.edit}
                        </Button>
                        <Button
                          size="sm"
                          variant="danger"
                          disabled={saving}
                          onClick={() => {
                            if (window.confirm(d.deleteConfirm)) {
                              void remove(guildId, feed.id);
                            }
                          }}
                        >
                          {d.delete}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="d-flex justify-content-end mt-3">
          <Button
            variant="primary"
            disabled={feeds.length >= maxFeeds || showForm}
            onClick={openCreate}
          >
            {d.addFeed}
          </Button>
        </div>
      </SectionCard>
      </MutedSection>
    </div>
  );
}
