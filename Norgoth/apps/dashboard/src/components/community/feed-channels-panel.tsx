"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  CAlert,
  CFormCheck,
  CFormLabel,
  CFormSelect,
  CSpinner,
} from "@coreui/react";
import {
  cilCalendar,
  cilFire,
  cilMediaPlay,
  cilRss,
  cilStar,
} from "@coreui/icons";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/layout/page-header";
import { Icon } from "@/components/ui/icon";
import { MiniFeatureCard } from "@/components/ui/mini-feature-card";
import { MutedSection } from "@/components/ui/feature-muting";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { DiscordEmojiPicker } from "@/components/discord/discord-emoji-picker";
import { GuildChannelMultiSelect } from "@/components/ui/guild-channel-multi-select";
import { ChannelSelect } from "@/components/ui/channel-select";
import { Slider } from "@/components/ui/slider";
import { NumberInput } from "@/components/ui/number-input";
import { useFirstGuild } from "@/lib/use-first-guild";
import { feedEmojiFromPicker, feedEmojiToPicker } from "@/lib/feed-emoji";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";
import {
  COUNTDOWN_PLACEHOLDER,
  formatCountdown,
  snapshotRemainingMs,
} from "@/lib/feed-countdown";
import {
  feedNeedsSetup,
  mergeFeedWindowCards,
  type FeedWindowCard,
} from "@/lib/feed-windows";
import { FeedChannelsSetupWizard } from "@/components/community/feed-channels-setup-wizard";
import {
  DEFAULT_FEED_CONFIG,
  type FeedConfig,
  type FeedWindowKey,
  useFeedChannelsStore,
} from "@/stores/feed-channels-store";

const WINDOW_ICONS: Record<FeedWindowKey, string[]> = {
  daily: cilMediaPlay,
  weekly: cilCalendar,
  monthly: cilStar,
  all_time: cilFire,
};

function clampDailyHours(value: number): number {
  return Math.max(1, Math.min(12, Math.round(value)));
}

export function FeedChannelsPanel() {
  const dict = useLocaleDict();
  const d = dict.feedChannelsPage;
  const cadenceCopy = dict.feedChannels;
  const notConfiguredLabel = d.notConfigured;

  const { guildId, resources, loading: guildLoading, error: guildError } =
    useFirstGuild();

  const config = useFeedChannelsStore((s) => s.config);
  const status = useFeedChannelsStore((s) => s.status);
  const loading = useFeedChannelsStore((s) => s.loading);
  const busy = useFeedChannelsStore((s) => s.busy);
  const error = useFeedChannelsStore((s) => s.error);
  const feedback = useFeedChannelsStore((s) => s.feedback);
  const load = useFeedChannelsStore((s) => s.load);
  const refreshStatus = useFeedChannelsStore((s) => s.refreshStatus);
  const save = useFeedChannelsStore((s) => s.save);
  const setEnabled = useFeedChannelsStore((s) => s.setEnabled);
  const patchWindow = useFeedChannelsStore((s) => s.patchWindow);
  const repair = useFeedChannelsStore((s) => s.repair);

  const [editingWindow, setEditingWindow] = useState<FeedWindowCard | null>(
    null
  );
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsDraft, setSettingsDraft] = useState<FeedConfig | null>(null);
  const [windowDraft, setWindowDraft] = useState<{
    channel_id: string;
    enabled: boolean;
  }>({ channel_id: "", enabled: false });
  const [intervalDraft, setIntervalDraft] = useState(1);
  const [intervalSaving, setIntervalSaving] = useState(false);
  const [countdownMs, setCountdownMs] = useState(0);
  const [countdownReady, setCountdownReady] = useState(false);
  const intervalDraftRef = useRef(intervalDraft);
  useEffect(() => {
    intervalDraftRef.current = intervalDraft;
  }, [intervalDraft]);

  // Canonical backend schedule only — never invent from slider draft.
  const countdownSnapshot = useMemo(
    () =>
      status
        ? {
            remainingSeconds: status.remaining_seconds ?? null,
            serverTime: status.server_time ?? null,
            nextRefreshAt: status.next_refresh_at ?? null,
            // Store stamps countdown_received_at on fetch; 0 means "no skew adjust".
            receivedAt: status.countdown_received_at ?? 0,
          }
        : null,
    [status]
  );

  const savedDailyHours = clampDailyHours(
    config?.windows?.daily?.refresh_interval_hours ??
      config?.daily_refresh_interval_hours ??
      Math.max(1, Math.round((config?.refresh_interval_minutes ?? 60) / 60))
  );

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
  }, [guildId, load]);

  useEffect(() => {
    setIntervalDraft(savedDailyHours);
  }, [savedDailyHours]);

  useEffect(() => {
    setCountdownReady(Boolean(status) && !loading);
  }, [status, loading]);

  // Display-only tick from backend remaining_seconds snapshot (skew-safe).
  useEffect(() => {
    const tick = () => {
      setCountdownMs(snapshotRemainingMs(countdownSnapshot));
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [countdownSnapshot]);

  // At zero: hold and quietly reconcile until backend advances next_refresh_at.
  // Must depend on countdownMs so we start polling when the tick reaches zero.
  useEffect(() => {
    if (!guildId || !countdownReady || !countdownSnapshot?.nextRefreshAt) return;
    if (countdownMs > 0) return;

    void refreshStatus(guildId);
    const id = window.setInterval(() => {
      void refreshStatus(guildId);
    }, 5_000);
    return () => window.clearInterval(id);
  }, [
    guildId,
    countdownReady,
    countdownMs,
    countdownSnapshot?.nextRefreshAt,
    refreshStatus,
  ]);

  // Tab focus: reconcile against backend (browser timer throttling).
  useEffect(() => {
    if (!guildId) return;
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        void refreshStatus(guildId);
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [guildId, refreshStatus]);

  const channels = resources?.channels ?? [];
  const categories = resources?.categories ?? [];
  const guildEmojis = resources?.emojis ?? [];
  const categoryMissing = Boolean(
    config?.feed_category_id &&
      !categories.some((c) => c.id === config.feed_category_id)
  );

  const windowCards = useMemo(
    () => mergeFeedWindowCards(config, status?.windows),
    [config, status?.windows]
  );

  const windowLabels: Record<FeedWindowKey, string> = {
    daily: d.windowDaily,
    weekly: d.windowWeekly,
    monthly: d.windowMonthly,
    all_time: d.windowAllTime,
  };

  const dailyConfigured = Boolean(config?.windows?.daily?.channel_id);
  const needsSetup = feedNeedsSetup(config);

  async function persistDailyHours(hours: number) {
    if (!guildId || !config) return;
    const next = clampDailyHours(hours);
    setIntervalDraft(next);
    if (next === savedDailyHours) return;
    setIntervalSaving(true);
    try {
      const saved = await save(guildId, {
        ...config,
        daily_refresh_interval_hours: next,
        refresh_interval_minutes: next * 60,
        windows: {
          ...config.windows,
          daily: {
            ...config.windows.daily,
            refresh_interval_hours: next,
          },
        },
      });
      if (saved) {
        setIntervalDraft(
          clampDailyHours(
            saved.windows?.daily?.refresh_interval_hours ??
              saved.daily_refresh_interval_hours ??
              next
          )
        );
      }
    } finally {
      setIntervalSaving(false);
    }
  }

  if (guildLoading || loading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          {d.loading}
        </div>
      </Card>
    );
  }

  if (guildError || !guildId) {
    return (
      <Card>
        <CAlert color="warning" className="mb-0">
          {guildError ?? d.botOffline}
        </CAlert>
      </Card>
    );
  }

  if (needsSetup || !config) {
    return (
      <div className="d-flex flex-column gap-4">
        <PageHeader
          title={d.title}
          icon={<Icon icon={cilRss} size="xl" />}
          category="community"
          description={d.description}
          infoKey="feedChannels"
        />
        <FeedChannelsSetupWizard
          guildId={guildId}
          channels={channels}
          categories={categories}
          guildEmojis={guildEmojis}
          onComplete={() => void load(guildId)}
        />
      </div>
    );
  }

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={d.title}
        icon={<Icon icon={cilRss} size="xl" />}
        category="community"
        description={d.descriptionUtc}
        infoKey="feedChannels"
        masterToggle={{
          enabled: config.enabled,
          onChange: (checked) => void setEnabled(guildId, checked),
          loading: busy,
          label: d.title,
        }}
      />

      <MutedSection enabled={config.enabled} className="d-flex flex-column gap-4">
        <div className="d-flex flex-wrap align-items-center justify-content-between gap-2">
          <div className="d-flex flex-wrap align-items-center gap-2">
            <Badge variant="info">
              {formatDict(d.tracked, { count: status?.tracked_messages ?? 0 })}
            </Badge>
            <Badge variant="neutral">
              {formatDict(d.votes, { count: status?.votes_total ?? 0 })}
            </Badge>
            {status?.top_message ? (
              <span className="small text-body-secondary">
                {formatDict(d.topNet, { score: status.top_message.net_score })}
              </span>
            ) : null}
          </div>
          <div className="d-flex flex-wrap align-items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={busy}
              onClick={() => {
                setSettingsDraft({ ...config });
                setSettingsOpen(true);
              }}
            >
              {d.globalSettings}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={busy}
              onClick={() => void repair(guildId)}
            >
              {busy ? d.repairing : (dict.featureInfo.feedChannels.repair ?? d.repair)}
            </Button>
          </div>
        </div>

        {error ? (
          <CAlert color="danger" className="mb-0 py-2">
            {error}
          </CAlert>
        ) : null}
        {feedback ? (
          <CAlert color="success" className="mb-0 py-2">
            {feedback}
          </CAlert>
        ) : null}
        {(status?.warnings ?? []).length > 0 ? (
          <CAlert color="warning" className="mb-0 py-2">
            {(status?.warnings ?? []).join(" · ")}
          </CAlert>
        ) : null}

        <div className="row row-cols-1 row-cols-md-2 row-cols-xl-4 g-3">
          {windowCards.map((card) => (
            <div key={card.key} className="col">
            <MiniFeatureCard
              icon={WINDOW_ICONS[card.key]}
              name={windowLabels[card.key]}
              category="community"
              description={
                card.configured
                  ? channels.find((c) => c.id === card.channel_id)?.name
                    ? `#${channels.find((c) => c.id === card.channel_id)?.name}`
                    : formatDict(d.channelFallback, {
                        id: card.channel_id ?? "",
                      })
                  : d.chooseDestination
              }
              status={card.configured ? (card.enabled ? "enabled" : "disabled") : "neutral"}
              statusLabel={
                card.configured
                  ? card.enabled
                    ? d.enabled
                    : d.disabled
                  : notConfiguredLabel
              }
              enabled={card.configured ? card.enabled : undefined}
              onToggle={
                card.configured
                  ? (checked) =>
                      void patchWindow(guildId, card.key, { enabled: checked })
                  : undefined
              }
              toggleDisabled={busy || !card.configured}
              onClick={() => {
                setEditingWindow(card);
                setWindowDraft({
                  channel_id: card.channel_id ?? "",
                  enabled: card.enabled,
                });
              }}
            />
            </div>
          ))}
        </div>

        <Card>
          <div className="d-flex flex-column gap-3">
            <div className="d-flex align-items-start justify-content-between gap-3 flex-wrap">
              <div>
                <h2 className="h6 mb-1 fw-semibold">
                  {cadenceCopy.dailySliderTitle}
                </h2>
                <p className="mb-0 small text-body-secondary">
                  {cadenceCopy.dailySliderHelp}
                </p>
              </div>
              <div
                className="text-end"
                title={d.countdownTitle}
              >
                <div className="small text-body-secondary">
                  {cadenceCopy.nextRefresh}
                </div>
                <div className="fw-semibold font-monospace">
                  {!countdownReady || !countdownSnapshot?.nextRefreshAt
                    ? COUNTDOWN_PLACEHOLDER
                    : formatCountdown(countdownMs)}
                </div>
              </div>
            </div>
            {dailyConfigured ? (
              <>
                <div className="d-flex align-items-center justify-content-between gap-3 flex-wrap">
                  <span className="small text-body-secondary">
                    1 {cadenceCopy.hours}
                  </span>
                  <span className="fw-semibold">
                    {cadenceCopy.currentHours}: {intervalDraft}{" "}
                    {cadenceCopy.hours}
                    {intervalSaving ? ` · ${cadenceCopy.saving}` : ""}
                  </span>
                  <span className="small text-body-secondary">
                    12 {cadenceCopy.hours}
                  </span>
                </div>
                <Slider
                  min={1}
                  max={12}
                  step={1}
                  value={intervalDraft}
                  disabled={busy || intervalSaving}
                  aria-label={cadenceCopy.dailySliderTitle}
                  onChange={(value) => setIntervalDraft(clampDailyHours(value))}
                  onPointerUp={() => {
                    const next = intervalDraftRef.current;
                    if (next !== savedDailyHours) {
                      void persistDailyHours(next);
                    }
                  }}
                />
                <div>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={
                      busy ||
                      intervalSaving ||
                      intervalDraft === savedDailyHours
                    }
                    onClick={() => void persistDailyHours(intervalDraft)}
                  >
                    {cadenceCopy.saveInterval}
                  </Button>
                </div>
              </>
            ) : (
              <p className="mb-0 small text-body-secondary" role="status">
                {cadenceCopy.configureDailyFirst}
              </p>
            )}
            <div className="small text-body-secondary d-flex flex-column gap-1">
              <span>{cadenceCopy.weeklyCadence}</span>
              <span>{cadenceCopy.monthlyCadence}</span>
              <span>{cadenceCopy.allTimeCadence}</span>
            </div>
          </div>
        </Card>

        <Card>
          <div className="d-flex flex-column gap-3">
            <div>
              <h2 className="h6 mb-1 fw-semibold">{d.feedCategoryTitle}</h2>
              <p className="mb-0 small text-body-secondary">
                {d.feedCategoryDesc}
              </p>
            </div>
            <div>
              <CFormLabel htmlFor="feed-category-select">{d.selectCategory}</CFormLabel>
              <CFormSelect
                id="feed-category-select"
                value={config.feed_category_id ?? ""}
                disabled={busy}
                aria-label={d.feedCategoryAria}
                onChange={(event) => {
                  const value = event.target.value || null;
                  void save(guildId, {
                    ...config,
                    feed_category_id: value,
                  });
                }}
              >
                <option value="">{d.noCategory}</option>
                {categoryMissing && config.feed_category_id ? (
                  <option value={config.feed_category_id}>
                    {formatDict(d.unavailableCategory, {
                      id: config.feed_category_id,
                    })}
                  </option>
                ) : null}
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </CFormSelect>
            </div>
            {categoryMissing ? (
              <CAlert color="warning" className="mb-0 py-2">
                {d.categoryMissingWarn}
              </CAlert>
            ) : null}
          </div>
        </Card>
      </MutedSection>

      <FeatureConfigurationModal
        visible={Boolean(editingWindow)}
        title={
          editingWindow
            ? formatDict(d.windowModalTitle, {
                window: windowLabels[editingWindow.key],
              })
            : d.windowModalFallback
        }
        description={d.windowModalDesc}
        category="community"
        icon={editingWindow ? WINDOW_ICONS[editingWindow.key] : cilRss}
        onClose={() => setEditingWindow(null)}
        saving={busy}
        onSave={async () => {
          if (!editingWindow) return;
          const saved = await patchWindow(guildId, editingWindow.key, {
            channel_id: windowDraft.channel_id || null,
            enabled: Boolean(windowDraft.channel_id) && windowDraft.enabled,
          });
          if (saved) setEditingWindow(null);
        }}
      >
        <div className="d-flex flex-column gap-3">
          <div>
            <CFormLabel>{d.feedChannel}</CFormLabel>
            <ChannelSelect
              channels={channels}
              value={windowDraft.channel_id}
              onChange={(value) =>
                setWindowDraft((draft) => ({
                  ...draft,
                  channel_id: value,
                  enabled: value ? draft.enabled || true : false,
                }))
              }
              emptyLabel={d.selectChannel}
            />
          </div>
          <CFormCheck
            label={d.enabled}
            checked={windowDraft.enabled && Boolean(windowDraft.channel_id)}
            disabled={!windowDraft.channel_id}
            onChange={(e) =>
              setWindowDraft((draft) => ({ ...draft, enabled: e.target.checked }))
            }
          />
        </div>
      </FeatureConfigurationModal>

      <FeatureConfigurationModal
        visible={settingsOpen && Boolean(settingsDraft)}
        title={d.settingsTitle}
        description={d.settingsDesc}
        category="community"
        icon={cilRss}
        onClose={() => setSettingsOpen(false)}
        saving={busy}
        onSave={async () => {
          if (!settingsDraft) return;
          const saved = await save(guildId, settingsDraft);
          if (saved) setSettingsOpen(false);
        }}
      >
        {settingsDraft ? (
          <div className="d-flex flex-column gap-3">
            <div>
              <CFormLabel>{d.upvoteEmoji}</CFormLabel>
              <DiscordEmojiPicker
                value={feedEmojiToPicker(settingsDraft.upvote_emoji)}
                guildEmojis={guildEmojis}
                onChange={(value) => {
                  const emoji = feedEmojiFromPicker(value);
                  if (!emoji) return;
                  setSettingsDraft((draft) =>
                    draft ? { ...draft, upvote_emoji: emoji } : draft
                  );
                }}
              />
            </div>
            <div>
              <CFormLabel>{d.downvoteEmoji}</CFormLabel>
              <DiscordEmojiPicker
                value={feedEmojiToPicker(settingsDraft.downvote_emoji)}
                guildEmojis={guildEmojis}
                onChange={(value) => {
                  const emoji = feedEmojiFromPicker(value);
                  if (!emoji) return;
                  setSettingsDraft((draft) =>
                    draft ? { ...draft, downvote_emoji: emoji } : draft
                  );
                }}
              />
            </div>
            <div>
              <CFormLabel>{d.sourceChannels}</CFormLabel>
              <GuildChannelMultiSelect
                channels={channels}
                selectedIds={settingsDraft.source_channel_ids}
                onChange={(ids) =>
                  setSettingsDraft((draft) =>
                    draft ? { ...draft, source_channel_ids: ids } : draft
                  )
                }
              />
            </div>
            <div>
              <CFormLabel>{d.excludedChannels}</CFormLabel>
              <GuildChannelMultiSelect
                channels={channels}
                selectedIds={settingsDraft.excluded_channel_ids}
                onChange={(ids) =>
                  setSettingsDraft((draft) =>
                    draft ? { ...draft, excluded_channel_ids: ids } : draft
                  )
                }
              />
            </div>
            <div className="row g-3">
              <div className="col-md-6">
                <CFormLabel>{d.minNetUpvotes}</CFormLabel>
                <NumberInput
                  value={settingsDraft.min_net_score}
                  defaultValue={DEFAULT_FEED_CONFIG.min_net_score}
                  min={0}
                  max={10000}
                  step={1}
                  aria-label={d.minNetUpvotes}
                  onCommit={(next) =>
                    setSettingsDraft((draft) =>
                      draft ? { ...draft, min_net_score: next } : draft
                    )
                  }
                />
              </div>
              <div className="col-md-6">
                <CFormLabel>{d.displayLimit}</CFormLabel>
                <NumberInput
                  value={settingsDraft.display_limit}
                  defaultValue={DEFAULT_FEED_CONFIG.display_limit}
                  min={1}
                  max={25}
                  step={1}
                  aria-label={d.displayLimit}
                  onCommit={(next) =>
                    setSettingsDraft((draft) =>
                      draft ? { ...draft, display_limit: next } : draft
                    )
                  }
                />
              </div>
            </div>
            <div>
              <CFormLabel htmlFor="feed-settings-category">{d.feedCategory}</CFormLabel>
              <CFormSelect
                id="feed-settings-category"
                value={settingsDraft.feed_category_id ?? ""}
                aria-label={d.feedCategoryAria}
                onChange={(event) =>
                  setSettingsDraft((draft) =>
                    draft
                      ? {
                          ...draft,
                          feed_category_id: event.target.value || null,
                        }
                      : draft
                  )
                }
              >
                <option value="">{d.noCategory}</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </CFormSelect>
            </div>
            <CFormCheck
              label={d.excludeBots}
              checked={settingsDraft.exclude_bots}
              onChange={(e) =>
                setSettingsDraft((draft) =>
                  draft ? { ...draft, exclude_bots: e.target.checked } : draft
                )
              }
            />
            <CFormCheck
              label={d.excludeWebhooks}
              checked={settingsDraft.exclude_webhooks}
              onChange={(e) =>
                setSettingsDraft((draft) =>
                  draft ? { ...draft, exclude_webhooks: e.target.checked } : draft
                )
              }
            />
            <CFormCheck
              label={d.excludeThreads}
              checked={settingsDraft.exclude_threads}
              onChange={(e) =>
                setSettingsDraft((draft) =>
                  draft ? { ...draft, exclude_threads: e.target.checked } : draft
                )
              }
            />
          </div>
        ) : null}
      </FeatureConfigurationModal>
    </div>
  );
}
