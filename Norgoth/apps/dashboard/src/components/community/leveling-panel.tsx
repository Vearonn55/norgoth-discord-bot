"use client";

import { useEffect, useMemo } from "react";
import {
  CAlert,
  CCol,
  CFormLabel,
  CFormSelect,
  CRow,
  CSpinner,
} from "@coreui/react";
import {
  cilBell,
  cilPeople,
  cilSettings,
  cilStar,
  cilTags,
} from "@coreui/icons";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/ui/data-table";
import { Icon } from "@/components/ui/icon";
import { MetricWidget } from "@/components/ui/metric-widget";
import { Slider } from "@/components/ui/slider";
import { NumberInput } from "@/components/ui/number-input";
import { EmbedEditor } from "@/components/discord/embed-editor";
import { EmbedWorkbench } from "@/components/discord/embed-workbench";
import { MessagePreview } from "@/components/discord/message-preview";
import { RichMessageEditor } from "@/components/editors/rich-message-editor";
import { PageHeader } from "@/components/layout/page-header";
import { MutedSection } from "@/components/ui/feature-muting";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useModulesStore } from "@/stores/modules-store";
import {
  useLevelingStore,
  type LevelingConfig,
  XP_PER_MESSAGE_MIN,
  XP_PER_MESSAGE_MAX,
  XP_MULTIPLIER_MIN,
  XP_MULTIPLIER_MAX,
  VOICE_XP_PER_MINUTE_MIN,
  VOICE_XP_PER_MINUTE_MAX,
  LEVEL_THRESHOLD_SCALE_MIN,
  LEVEL_THRESHOLD_SCALE_MAX,
  xpForLevel,
} from "@/stores/leveling-store";

const ANNOUNCE_MODE_LABELS: Record<LevelingConfig["announce_mode"], string> = {
  current: "Member's channel",
  channel: "Fixed channel",
  off: "Disabled",
};

export function LevelingPanel() {
  const params = useParams();
  const lang = typeof params?.lang === "string" ? params.lang : "en";
  const { guildId, resources, loading, error, reload } = useFirstGuild();

  const config = useLevelingStore((s) => s.config);
  const leaderboard = useLevelingStore((s) => s.leaderboard);
  const saving = useLevelingStore((s) => s.saving);
  const feedback = useLevelingStore((s) => s.feedback);
  const feedbackIsError = useLevelingStore((s) => s.feedbackIsError);
  const newRewardLevel = useLevelingStore((s) => s.newRewardLevel);
  const newRewardRoleId = useLevelingStore((s) => s.newRewardRoleId);
  const rewardSearch = useLevelingStore((s) => s.rewardSearch);
  const rewardPage = useLevelingStore((s) => s.rewardPage);
  const setConfig = useLevelingStore((s) => s.setConfig);
  const setLevelUpMessage = useLevelingStore((s) => s.setLevelUpMessage);
  const setRewardSearch = useLevelingStore((s) => s.setRewardSearch);
  const setRewardPage = useLevelingStore((s) => s.setRewardPage);
  const setNewRewardLevel = useLevelingStore((s) => s.setNewRewardLevel);
  const setNewRewardRoleId = useLevelingStore((s) => s.setNewRewardRoleId);
  const setFeedback = useLevelingStore((s) => s.setFeedback);
  const loadData = useLevelingStore((s) => s.load);
  const saveStore = useLevelingStore((s) => s.save);
  const addReward = useLevelingStore((s) => s.addReward);

  const modules = useModulesStore((s) => s.modules);
  const modulesPending = useModulesStore((s) => s.pendingKey);
  const loadModules = useModulesStore((s) => s.load);
  const toggleModule = useModulesStore((s) => s.toggleModule);

  // The shared per-guild module flag is the authoritative on/off state for
  // leveling; the bot already gates message + voice XP on it. Default to
  // enabled (matching the backend default) until the flags load.
  const levelingModule = modules.find((module) => module.key === "leveling");
  const levelingEnabled = levelingModule?.enabled ?? true;

  useEffect(() => {
    if (!guildId) return;
    void loadData(guildId);
    void loadModules(guildId);
  }, [guildId, loadData, loadModules]);

  async function save() {
    if (!guildId) return;
    await saveStore(guildId);
  }

  const channels = resources?.channels ?? [];
  const roles = (resources?.roles ?? []).filter((role) => !role.managed);
  const roleNames = useMemo(
    () => new Map(roles.map((role) => [role.id, role.name])),
    [roles]
  );
  const roleColors = useMemo(
    () => new Map(roles.map((role) => [role.id, role.color])),
    [roles]
  );

  const effectiveXp = useMemo(
    () => Math.max(1, Math.round(config.xp_per_message * config.xp_multiplier)),
    [config.xp_per_message, config.xp_multiplier]
  );
  // A per-minute value of 0 means voice XP is disabled, so the effective value
  // is 0 (not floored to 1). Any positive base keeps the shared min-1 rule.
  const voiceXpDisabled = config.voice_xp_per_minute <= 0;
  const effectiveVoiceXp = useMemo(
    () =>
      voiceXpDisabled
        ? 0
        : Math.max(
            1,
            Math.round(config.voice_xp_per_minute * config.xp_multiplier)
          ),
    [voiceXpDisabled, config.voice_xp_per_minute, config.xp_multiplier]
  );

  const scale = config.level_threshold_scale;
  const level2Step = useMemo(
    () => xpForLevel(2, scale) - xpForLevel(1, scale),
    [scale]
  );
  const totalToLevel5 = useMemo(() => xpForLevel(5, scale), [scale]);

  function handleAddOrUpdateReward() {
    if (!newRewardRoleId) {
      setFeedback("Select a role to grant before adding a reward.", true);
      return;
    }
    const replacing = config.reward_roles.some(
      (reward) => reward.level === newRewardLevel
    );
    addReward();
    setFeedback(
      replacing
        ? `Updated the reward for level ${newRewardLevel}.`
        : `Added a reward at level ${newRewardLevel}.`,
      false
    );
  }

  function handleEditReward(level: number, roleId: string) {
    setNewRewardLevel(level);
    setNewRewardRoleId(roleId);
    setFeedback(
      `Editing the level ${level} reward — adjust the fields and click "Add Level Reward" to save.`,
      false
    );
  }

  const filteredRewards = useMemo(() => {
    const query = rewardSearch.trim().toLowerCase();
    const rows = [...config.reward_roles].sort((a, b) => a.level - b.level);
    if (!query) return rows;
    return rows.filter((reward) => {
      const roleName = roleNames.get(reward.role_id) ?? reward.role_id;
      return (
        String(reward.level).includes(query) ||
        roleName.toLowerCase().includes(query)
      );
    });
  }, [config.reward_roles, rewardSearch, roleNames]);

  if (loading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          Loading leveling settings…
        </div>
      </Card>
    );
  }

  if (error || !guildId) {
    return (
      <Card>
        <div className="d-flex flex-column gap-3">
          <Badge variant="warning">Bot required</Badge>
          <p className="mb-0 small text-body-secondary">{error}</p>
          <div>
            <Button variant="secondary" onClick={() => void reload()}>
              Retry
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Levels & Activity"
        icon={<Icon icon={cilStar} size="xl" />}
        category="leveling"
        description="Message and voice XP with level progression, level-up announcements, and role rewards."
        infoKey="leveling"
        masterToggle={{
          enabled: levelingEnabled,
          onChange: (checked) =>
            guildId && void toggleModule(guildId, "leveling", checked),
          loading: modulesPending === "leveling",
        }}
      />

      <MutedSection enabled={levelingEnabled} className="d-flex flex-column gap-4">
      <div className="row g-3">
        <div className="col-6 col-xl-3">
          <MetricWidget
            label="Ranked Members"
            value={leaderboard.length}
            accent="primary"
            icon={<Icon icon={cilPeople} size="lg" />}
          />
        </div>
        <div className="col-6 col-xl-3">
          <MetricWidget
            label="Reward Roles"
            value={config.reward_roles.length}
            accent="warning"
            icon={<Icon icon={cilTags} size="lg" />}
          />
        </div>
        <div className="col-6 col-xl-3">
          <MetricWidget
            label="Announce Mode"
            value={ANNOUNCE_MODE_LABELS[config.announce_mode]}
            accent={config.announce_mode === "off" ? "danger" : "success"}
            icon={<Icon icon={cilBell} size="lg" />}
          />
        </div>
        <div className="col-6 col-xl-3">
          <MetricWidget
            label="Top Level"
            value={leaderboard[0]?.level ?? 0}
            helper={leaderboard[0]?.name ?? "No ranked members yet"}
            accent="info"
            icon={<Icon icon={cilStar} size="lg" />}
          />
        </div>
      </div>

      {/* XP Configuration */}
      <Card>
        <div className="d-flex flex-column gap-3">
          <div className="d-flex align-items-start gap-3">
            <Icon icon={cilSettings} size="lg" className="text-body-secondary mt-1" />
            <div>
              <h2 className="h5 mb-0 fw-semibold">XP Configuration</h2>
              <p className="mt-1 mb-0 small text-body-secondary">
                Members earn XP for messages (once per minute) and, when enabled,
                for time spent in voice. Tune the base amounts and the shared
                multiplier below.
              </p>
            </div>
          </div>

          <CRow className="g-4 align-items-start">
            <CCol md={4}>
              <div className="d-flex flex-column gap-3">
                <div>
                  <CFormLabel htmlFor="xp-per-message" className="fw-semibold">
                    Message XP per Message
                  </CFormLabel>
                  <NumberInput
                    id="xp-per-message"
                    value={config.xp_per_message}
                    defaultValue={XP_PER_MESSAGE_MIN}
                    min={XP_PER_MESSAGE_MIN}
                    max={XP_PER_MESSAGE_MAX}
                    step={1}
                    aria-label="Message XP per message"
                    onCommit={(next) =>
                      setConfig((current) => ({
                        ...current,
                        xp_per_message: next,
                      }))
                    }
                  />
                  <p className="small text-body-secondary mt-1 mb-0">
                    Base XP per eligible message ({XP_PER_MESSAGE_MIN}–
                    {XP_PER_MESSAGE_MAX}).
                  </p>
                </div>
              </div>
            </CCol>

            <CCol md={4}>
              <div className="d-flex flex-column gap-3">
                <div>
                  <CFormLabel
                    htmlFor="voice-xp-per-minute"
                    className="fw-semibold"
                  >
                    Voice XP per Minute
                  </CFormLabel>
                  <NumberInput
                    id="voice-xp-per-minute"
                    value={config.voice_xp_per_minute}
                    defaultValue={VOICE_XP_PER_MINUTE_MIN}
                    min={VOICE_XP_PER_MINUTE_MIN}
                    max={VOICE_XP_PER_MINUTE_MAX}
                    step={1}
                    aria-label="Voice XP per minute"
                    onCommit={(next) =>
                      setConfig((current) => ({
                        ...current,
                        voice_xp_per_minute: next,
                      }))
                    }
                  />
                  {voiceXpDisabled ? (
                    <p className="small text-body-tertiary mt-1 mb-0">
                      Voice Chat XP is disabled when this value is 0.
                    </p>
                  ) : (
                    <p className="small text-body-secondary mt-1 mb-0">
                      XP per minute in voice. Bots, AFK, deafened and
                      server-muted members are excluded.
                    </p>
                  )}
                </div>
              </div>
            </CCol>

            <CCol md={4}>
              <CFormLabel className="fw-semibold">Effective XP</CFormLabel>
              <div className="d-flex flex-column gap-2">
                <div className="border rounded px-3 py-3 text-center">
                  <div className="h4 mb-0 fw-semibold text-info">
                    {effectiveXp}
                  </div>
                  <div className="small text-body-secondary">per message</div>
                </div>
                <div className="border rounded px-3 py-3 text-center">
                  <div
                    className={`h4 mb-0 fw-semibold ${
                      voiceXpDisabled ? "text-body-tertiary" : "text-info"
                    }`}
                  >
                    {effectiveVoiceXp}
                  </div>
                  <div className="small text-body-secondary">
                    {voiceXpDisabled ? "per minute (off)" : "per minute"}
                  </div>
                </div>
                <div className="border rounded px-3 py-2">
                  <div className="small text-body-secondary mb-1 fw-semibold">
                    Level thresholds (scale {scale.toFixed(2)}x)
                  </div>
                  <div className="d-flex justify-content-between small">
                    <span className="text-body-secondary">Level 2 needs</span>
                    <span className="fw-semibold">
                      {level2Step.toLocaleString()} XP
                    </span>
                  </div>
                  <div className="d-flex justify-content-between small">
                    <span className="text-body-secondary">Total to Level 5</span>
                    <span className="fw-semibold">
                      {totalToLevel5.toLocaleString()} XP
                    </span>
                  </div>
                </div>
              </div>
            </CCol>
          </CRow>

          <CRow className="g-4 align-items-start">
            <CCol md={8}>
              <div className="d-flex align-items-center justify-content-between">
                <CFormLabel htmlFor="xp-multiplier" className="mb-0 fw-semibold">
                  XP Multiplier
                </CFormLabel>
                <span className="fw-semibold">
                  {config.xp_multiplier.toFixed(1)}x
                </span>
              </div>
              <div className="mt-2">
                <Slider
                  id="xp-multiplier"
                  min={XP_MULTIPLIER_MIN}
                  max={XP_MULTIPLIER_MAX}
                  step={0.1}
                  value={config.xp_multiplier}
                  onChange={(next) =>
                    setConfig((current) => ({
                      ...current,
                      xp_multiplier: next,
                    }))
                  }
                  aria-label="XP multiplier"
                />
                <div className="d-flex justify-content-between small text-body-tertiary">
                  <span>{XP_MULTIPLIER_MIN.toFixed(1)}x</span>
                  <span>
                    {((XP_MULTIPLIER_MIN + XP_MULTIPLIER_MAX) / 2).toFixed(1)}x
                  </span>
                  <span>{XP_MULTIPLIER_MAX.toFixed(1)}x</span>
                </div>
              </div>
              <p className="small text-body-secondary mt-1 mb-0">
                Applies to both message and voice XP. It does not change the
                once-per-minute cooldown or anti-spam eligibility.
              </p>
            </CCol>
          </CRow>

          <CRow className="g-4 align-items-start">
            <CCol md={8}>
              <div className="d-flex align-items-center justify-content-between">
                <CFormLabel
                  htmlFor="level-threshold-scale"
                  className="mb-0 fw-semibold"
                >
                  Level Up Threshold Scale
                </CFormLabel>
                <span className="fw-semibold">{scale.toFixed(2)}x</span>
              </div>
              <div className="mt-2">
                <Slider
                  id="level-threshold-scale"
                  min={LEVEL_THRESHOLD_SCALE_MIN}
                  max={LEVEL_THRESHOLD_SCALE_MAX}
                  step={0.05}
                  value={scale}
                  onChange={(next) =>
                    setConfig((current) => ({
                      ...current,
                      level_threshold_scale: next,
                    }))
                  }
                  aria-label="Level up threshold scale"
                />
                <div className="d-flex justify-content-between small text-body-tertiary">
                  <span>{LEVEL_THRESHOLD_SCALE_MIN.toFixed(2)}x</span>
                  <span>
                    {(
                      (LEVEL_THRESHOLD_SCALE_MIN + LEVEL_THRESHOLD_SCALE_MAX) /
                      2
                    ).toFixed(2)}
                    x
                  </span>
                  <span>{LEVEL_THRESHOLD_SCALE_MAX.toFixed(2)}x</span>
                </div>
              </div>
              <p className="small text-body-secondary mt-1 mb-0">
                Controls how fast level requirements grow. Higher values make
                each level take more XP. Existing XP is preserved — members&apos;
                levels are recalculated live from the new curve.
              </p>
            </CCol>
          </CRow>
        </div>
      </Card>

      {/* Level-Up Message (always an embed) */}
      <Card>
        <div className="d-flex flex-column gap-3">
          <div className="d-flex align-items-start gap-3">
            <Icon icon={cilBell} size="lg" className="text-body-secondary mt-1" />
            <div>
              <h2 className="h5 mb-0 fw-semibold">Level-Up Message</h2>
              <p className="mt-1 mb-0 small text-body-secondary">
                Sent as a Discord embed. Compose the body below — it becomes the
                embed description. Variables: {"{user}"}, {"{username}"},{" "}
                {"{level}"}, {"{server}"}.
              </p>
            </div>
          </div>

          <CRow className="g-3">
            <CCol md={6}>
              <CFormLabel>Level-up announcements</CFormLabel>
              <CFormSelect
                value={config.announce_mode}
                onChange={(event) =>
                  setConfig((current) => ({
                    ...current,
                    announce_mode: event.target
                      .value as LevelingConfig["announce_mode"],
                  }))
                }
              >
                <option value="current">In the member&apos;s channel</option>
                <option value="channel">In a fixed channel</option>
                <option value="off">Disabled</option>
              </CFormSelect>
            </CCol>

            {config.announce_mode === "channel" ? (
              <CCol md={6}>
                <CFormLabel>Announcement channel</CFormLabel>
                <CFormSelect
                  value={config.announce_channel_id ?? ""}
                  onChange={(event) =>
                    setConfig((current) => ({
                      ...current,
                      announce_channel_id: event.target.value || null,
                    }))
                  }
                >
                  <option value="">Select a channel…</option>
                  {channels.map((channel) => (
                    <option key={channel.id} value={channel.id}>
                      #{channel.name}
                    </option>
                  ))}
                </CFormSelect>
              </CCol>
            ) : null}
          </CRow>

          <EmbedWorkbench
            editor={
              <div className="d-flex flex-column gap-3">
                <div>
                  <CFormLabel>Message (embed body)</CFormLabel>
                  <RichMessageEditor
                    value={config.level_up_message}
                    onChange={(markdown) => setLevelUpMessage(markdown)}
                    variables={["{user}", "{username}", "{level}", "{server}"]}
                  />
                </div>
                <EmbedEditor
                  value={config.level_up_embed}
                  guildId={guildId ?? undefined}
                  hideDescription
                  onChange={(embed) =>
                    setConfig((current) => ({
                      ...current,
                      level_up_embed: embed,
                    }))
                  }
                />
              </div>
            }
            preview={
              <MessagePreview
                embed={{
                  ...config.level_up_embed,
                  title: (config.level_up_embed.title || "").replaceAll(
                    "{level}",
                    "5"
                  ),
                  description: (config.level_up_message || "")
                    .replaceAll("{user}", "@Member")
                    .replaceAll("{username}", "Member")
                    .replaceAll("{level}", "5")
                    .replaceAll("{server}", "Server"),
                  footer: (config.level_up_embed.footer || "").replaceAll(
                    "{server}",
                    "Server"
                  ),
                }}
                mode="embed"
                showImagePlaceholders
              />
            }
          />
        </div>
      </Card>

      {/* Role Rewards */}
      <Card>
        <div className="d-flex flex-column gap-3">
          <div className="d-flex align-items-start gap-3">
            <Icon icon={cilTags} size="lg" className="text-body-secondary mt-1" />
            <div>
              <h2 className="h5 mb-0 fw-semibold">Role Rewards</h2>
              <p className="mt-1 mb-0 small text-body-secondary">
                Automatically grant roles when members reach a level.
              </p>
            </div>
          </div>

          <div className="d-flex flex-column gap-3">

            {config.reward_roles.length === 0 ? (
              <p className="mb-0 small text-body-secondary">
                No role rewards configured.
              </p>
            ) : (
              <DataTable
                columns={[
                  {
                    key: "level",
                    header: "Level",
                    cell: (row) => row.level,
                  },
                  {
                    key: "role",
                    header: "Role",
                    cell: (row) => {
                      const name = roleNames.get(row.role_id) ?? row.role_id;
                      const color = roleColors.get(row.role_id);
                      const hasColor = Boolean(color && color !== "#000000");
                      return (
                        <span className="d-inline-flex align-items-center gap-2">
                          <span
                            aria-hidden
                            style={{
                              width: 10,
                              height: 10,
                              borderRadius: "50%",
                              display: "inline-block",
                              backgroundColor: hasColor
                                ? color
                                : "var(--cui-border-color-translucent, #6b7280)",
                            }}
                          />
                          @{name}
                        </span>
                      );
                    },
                  },
                  {
                    key: "actions",
                    header: "",
                    className: "text-end",
                    cell: (row) => (
                      <div className="d-inline-flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEditReward(row.level, row.role_id)}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setConfig((current) => ({
                              ...current,
                              reward_roles: current.reward_roles.filter(
                                (item) =>
                                  !(
                                    item.level === row.level &&
                                    item.role_id === row.role_id
                                  )
                              ),
                            }))
                          }
                        >
                          Remove
                        </Button>
                      </div>
                    ),
                  },
                ]}
                rows={filteredRewards}
                rowKey={(row) => `${row.level}-${row.role_id}`}
                emptyMessage="No matching rewards."
                search={rewardSearch}
                onSearchChange={setRewardSearch}
                searchPlaceholder="Search rewards…"
                page={rewardPage}
                pageSize={10}
                onPageChange={setRewardPage}
              />
            )}

            <div className="d-flex flex-wrap align-items-end gap-3">
              <div>
                <CFormLabel className="small text-body-secondary">
                  At level
                </CFormLabel>
                <NumberInput
                  value={newRewardLevel}
                  defaultValue={1}
                  min={1}
                  max={1000}
                  step={1}
                  aria-label="Reward level"
                  className="w-auto"
                  onCommit={(next) => setNewRewardLevel(next)}
                />
              </div>

              <div style={{ minWidth: 192 }}>
                <CFormLabel className="small text-body-secondary">
                  Grant role
                </CFormLabel>
                <CFormSelect
                  value={newRewardRoleId}
                  onChange={(event) => setNewRewardRoleId(event.target.value)}
                >
                  <option value="">Select a role…</option>
                  {roles.map((role) => (
                    <option key={role.id} value={role.id}>
                      @{role.name}
                    </option>
                  ))}
                </CFormSelect>
              </div>

              <Button variant="secondary" onClick={handleAddOrUpdateReward}>
                Add Level Reward
              </Button>
            </div>
          </div>

          <div className="d-flex align-items-center gap-3 flex-wrap">
            <Button
              variant="primary"
              onClick={() => void save()}
              disabled={saving || !levelingEnabled}
            >
              {saving ? "Saving…" : "Save Leveling Settings"}
            </Button>

            {feedback ? (
              <CAlert
                color={feedbackIsError ? "danger" : "success"}
                className="mb-0 py-2 px-3 small"
              >
                {feedback}
              </CAlert>
            ) : null}
          </div>
        </div>
      </Card>

      <Card>
        <div className="d-flex flex-wrap align-items-center justify-content-between gap-3">
          <div>
            <h2 className="h5 mb-1 fw-semibold">Leaderboard</h2>
            <p className="mb-0 small text-body-secondary">
              Top members by XP live on a dedicated page.{" "}
              {leaderboard.length
                ? `${leaderboard.length} ranked · top level ${leaderboard[0]?.level ?? 0}.`
                : "Nobody has earned XP yet."}
            </p>
          </div>
          <Link
            href={`/${lang}/community/leaderboard`}
            className="btn btn-outline-secondary btn-sm"
          >
            View Leaderboard
          </Link>
        </div>
      </Card>
      </MutedSection>
    </div>
  );
}
