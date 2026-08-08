"use client";

import { useEffect, useMemo } from "react";
import {
  CAlert,
  CCol,
  CFormInput,
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
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/ui/data-table";
import { Icon } from "@/components/ui/icon";
import { MetricWidget } from "@/components/ui/metric-widget";
import { Slider } from "@/components/ui/slider";
import { EmbedEditor } from "@/components/discord/embed-editor";
import { EmbedWorkbench } from "@/components/discord/embed-workbench";
import { MessagePreview } from "@/components/discord/message-preview";
import { RichMessageEditor } from "@/components/editors/rich-message-editor";
import { useFirstGuild } from "@/lib/use-first-guild";
import {
  useLevelingStore,
  type LevelingConfig,
  XP_PER_MESSAGE_MIN,
  XP_PER_MESSAGE_MAX,
  XP_MULTIPLIER_MIN,
  XP_MULTIPLIER_MAX,
} from "@/stores/leveling-store";

export function LevelingPanel() {
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
  const leaderboardSearch = useLevelingStore((s) => s.leaderboardSearch);
  const leaderboardPage = useLevelingStore((s) => s.leaderboardPage);
  const setConfig = useLevelingStore((s) => s.setConfig);
  const setLevelUpMessage = useLevelingStore((s) => s.setLevelUpMessage);
  const setRewardSearch = useLevelingStore((s) => s.setRewardSearch);
  const setRewardPage = useLevelingStore((s) => s.setRewardPage);
  const setLeaderboardSearch = useLevelingStore((s) => s.setLeaderboardSearch);
  const setLeaderboardPage = useLevelingStore((s) => s.setLeaderboardPage);
  const setNewRewardLevel = useLevelingStore((s) => s.setNewRewardLevel);
  const setNewRewardRoleId = useLevelingStore((s) => s.setNewRewardRoleId);
  const loadData = useLevelingStore((s) => s.load);
  const saveStore = useLevelingStore((s) => s.save);
  const addReward = useLevelingStore((s) => s.addReward);

  useEffect(() => {
    if (!guildId) return;
    void loadData(guildId);
  }, [guildId, loadData]);

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

  const effectiveXp = useMemo(
    () => Math.max(1, Math.round(config.xp_per_message * config.xp_multiplier)),
    [config.xp_per_message, config.xp_multiplier]
  );

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

  const filteredLeaderboard = useMemo(() => {
    const query = leaderboardSearch.trim().toLowerCase();
    if (!query) return leaderboard;
    return leaderboard.filter((entry) =>
      entry.name.toLowerCase().includes(query)
    );
  }, [leaderboard, leaderboardSearch]);

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
            value={config.announce_mode}
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
                Members earn XP per eligible message (once per minute). Tune the
                base amount and multiplier below.
              </p>
            </div>
          </div>

          <CRow className="g-4 align-items-start">
            <CCol md={4}>
              <CFormLabel htmlFor="xp-per-message">XP Per Message</CFormLabel>
              <CFormInput
                id="xp-per-message"
                type="number"
                min={XP_PER_MESSAGE_MIN}
                max={XP_PER_MESSAGE_MAX}
                step={1}
                value={config.xp_per_message}
                onChange={(event) => {
                  const raw = Number(event.target.value);
                  const clamped = Number.isFinite(raw)
                    ? Math.min(
                        XP_PER_MESSAGE_MAX,
                        Math.max(XP_PER_MESSAGE_MIN, Math.round(raw)),
                      )
                    : XP_PER_MESSAGE_MIN;
                  setConfig((current) => ({
                    ...current,
                    xp_per_message: clamped,
                  }));
                }}
              />
              <p className="small text-body-secondary mt-1 mb-0">
                Base XP awarded per eligible message ({XP_PER_MESSAGE_MIN}–
                {XP_PER_MESSAGE_MAX}).
              </p>
            </CCol>

            <CCol md={5}>
              <div className="d-flex align-items-center justify-content-between">
                <CFormLabel htmlFor="xp-multiplier" className="mb-0">
                  XP Multiplier
                </CFormLabel>
                <span className="fw-semibold">
                  {config.xp_multiplier.toFixed(1)}x
                </span>
              </div>
              <div className="mt-2" style={{ maxWidth: 320 }}>
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
                Scales reward magnitude only. It does not change the
                once-per-minute cooldown or anti-spam eligibility.
              </p>
            </CCol>

            <CCol md={3}>
              <CFormLabel>Effective XP</CFormLabel>
              <div className="border rounded px-3 py-3 text-center">
                <div className="h4 mb-0 fw-semibold text-info">{effectiveXp}</div>
                <div className="small text-body-secondary">
                  XP per eligible message
                </div>
              </div>
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
                showEmbed
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
                    cell: (row) =>
                      `@${roleNames.get(row.role_id) ?? row.role_id}`,
                  },
                  {
                    key: "actions",
                    header: "",
                    className: "text-end",
                    cell: (row) => (
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
                <CFormInput
                  type="number"
                  min={1}
                  max={1000}
                  value={newRewardLevel}
                  onChange={(event) => {
                    const parsed = Number(event.target.value);
                    if (!Number.isNaN(parsed)) {
                      setNewRewardLevel(
                        Math.min(1000, Math.max(1, Math.round(parsed)))
                      );
                    }
                  }}
                  style={{ width: 96 }}
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

              <Button variant="secondary" onClick={addReward}>
                Add Reward
              </Button>
            </div>
          </div>

          <div className="d-flex align-items-center gap-3 flex-wrap">
            <Button
              variant="primary"
              onClick={() => void save()}
              disabled={saving}
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
        <div className="d-flex flex-column gap-3">
          <div className="d-flex align-items-center justify-content-between gap-3">
            <div className="d-flex align-items-start gap-3">
              <Icon icon={cilStar} size="lg" className="text-body-secondary mt-1" />
              <div>
                <h2 className="h5 mb-0 fw-semibold">Leaderboard</h2>
                <p className="mt-1 mb-0 small text-body-secondary">
                  Top members by XP. Members can also use /rank, /leaderboard, and
                  /give-xp (Manage Server) in Discord.
                </p>
              </div>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => guildId && void loadData(guildId)}
            >
              Refresh
            </Button>
          </div>

          {leaderboard.length === 0 ? (
            <CAlert color="secondary" className="mb-0">
              Nobody has earned XP yet. XP is granted as members chat.
            </CAlert>
          ) : (
            <DataTable
              columns={[
                {
                  key: "rank",
                  header: "#",
                  cell: (row) => `#${row.rank}`,
                },
                {
                  key: "name",
                  header: "Member",
                  cell: (row) => row.name,
                },
                {
                  key: "level",
                  header: "Level",
                  cell: (row) => (
                    <Badge variant="info">Level {row.level}</Badge>
                  ),
                },
                {
                  key: "xp",
                  header: "XP",
                  cell: (row) => row.xp.toLocaleString(),
                },
              ]}
              rows={filteredLeaderboard}
              rowKey={(row) => row.user_id}
              emptyMessage="No matching members."
              search={leaderboardSearch}
              onSearchChange={setLeaderboardSearch}
              searchPlaceholder="Search members…"
              page={leaderboardPage}
              pageSize={10}
              onPageChange={setLeaderboardPage}
            />
          )}
        </div>
      </Card>
    </div>
  );
}
