"use client";

import { useEffect, useState } from "react";
import {
  CFormLabel,
  CSpinner,
} from "@coreui/react";
import { SectionCard } from "@/components/ui/section-card";
import { ChannelSelect } from "@/components/ui/channel-select";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { NumberInput } from "@/components/ui/number-input";
import { MutedSection } from "@/components/ui/feature-muting";
import { PageHeader } from "@/components/layout/page-header";
import { PageActionFooter } from "@/components/layout/page-action-footer";
import { useFirstGuild } from "@/stores/guild-store";
import { useRaidStore, type RaidConfig } from "@/stores/raid-store";
import { Icon } from "@/components/ui/icon";
import { cilShieldAlt } from "@coreui/icons";
import { useLocaleDict } from "@/lib/locale-dict";

export function RaidProtectionPanel() {
  const dict = useLocaleDict();
  const d = dict.raidPage;
  const { guildId, resources, loading: guildLoading } = useFirstGuild();
  const config = useRaidStore((s) => s.config);
  const incidents = useRaidStore((s) => s.incidents);
  const loading = useRaidStore((s) => s.loading);
  const saving = useRaidStore((s) => s.saving);
  const error = useRaidStore((s) => s.error);
  const load = useRaidStore((s) => s.load);
  const save = useRaidStore((s) => s.save);
  const loadIncidents = useRaidStore((s) => s.loadIncidents);
  const [draft, setDraft] = useState<RaidConfig | null>(null);

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
    void loadIncidents(guildId);
  }, [guildId, load, loadIncidents]);

  useEffect(() => {
    if (config) setDraft(config);
  }, [config]);

  if (guildLoading || loading || !draft) {
    return (
      <div className="d-flex align-items-center gap-2">
        <CSpinner size="sm" /> {d.loading}
      </div>
    );
  }

  if (!guildId) {
    return <p className="text-body-secondary">{d.selectServer}</p>;
  }

  function patch(partial: Partial<RaidConfig>) {
    setDraft((prev) => (prev ? { ...prev, ...partial } : prev));
  }

  // The master switch is authoritative and persists immediately so the
  // disabled state is saved even while the page-level Save is disabled.
  async function setEnabledAndSave(checked: boolean) {
    if (!draft || !guildId) return;
    const next = { ...draft, enabled: checked };
    setDraft(next);
    await save(guildId, next);
  }

  const dirty = JSON.stringify(draft) !== JSON.stringify(config);

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={d.title}
        category="security"
        icon={<Icon icon={cilShieldAlt} size="xl" />}
        description={d.description}
        infoKey="raidProtection"
        masterToggle={{
          enabled: draft.enabled,
          onChange: (checked) => void setEnabledAndSave(checked),
          loading: saving,
        }}
      />

      {error ? <p className="text-danger">{error}</p> : null}

      {draft.active_incident ? (
        <div className="alert alert-warning mb-0">
          {d.activeIncident}
        </div>
      ) : null}

      <MutedSection enabled={draft.enabled} className="d-flex flex-column gap-4">
      <SectionCard level="primary" category="security" header={d.detectionHeader}>
        <div className="d-flex flex-column gap-3 p-1">
          <div>
            <CFormLabel>{d.alertChannel}</CFormLabel>
            <ChannelSelect
              channels={resources?.channels ?? []}
              value={draft.alert_channel_id ?? ""}
              onChange={(v) => patch({ alert_channel_id: v || null })}
            />
          </div>
          <div style={{ maxWidth: 420 }}>
            <div className="d-flex align-items-center justify-content-between">
              <CFormLabel className="mb-0">{d.joinsPerMinute}</CFormLabel>
              <span className="fw-semibold">{draft.joins_per_minute}</span>
            </div>
            <Slider
              min={2}
              max={100}
              value={draft.joins_per_minute}
              onChange={(value) => patch({ joins_per_minute: value })}
              aria-label={d.joinsPerMinuteAria}
            />
          </div>
          <div style={{ maxWidth: 420 }}>
            <div className="d-flex align-items-center justify-content-between">
              <CFormLabel className="mb-0">{d.youngAccountAge}</CFormLabel>
              <span className="fw-semibold">
                {draft.young_account_age_days}
              </span>
            </div>
            <Slider
              min={1}
              max={90}
              value={draft.young_account_age_days}
              onChange={(value) => patch({ young_account_age_days: value })}
              aria-label={d.youngAccountAgeAria}
            />
          </div>
          <div style={{ maxWidth: 420 }}>
            <div className="d-flex align-items-center justify-content-between">
              <CFormLabel className="mb-0">{d.youngAccountRatio}</CFormLabel>
              <span className="fw-semibold">{draft.young_account_ratio}</span>
            </div>
            <Slider
              min={0}
              max={100}
              value={draft.young_account_ratio}
              onChange={(value) => patch({ young_account_ratio: value })}
              aria-label={d.youngAccountRatioAria}
            />
          </div>
          <div>
            <CFormLabel>{d.responseDuration}</CFormLabel>
            <NumberInput
              value={draft.response_duration_minutes}
              defaultValue={5}
              min={1}
              max={1440}
              step={1}
              aria-label={d.responseDurationAria}
              onCommit={(next) => patch({ response_duration_minutes: next })}
            />
          </div>
        </div>
      </SectionCard>

      <SectionCard level="primary" category="security" header={d.responseHeader}>
        <div className="d-flex flex-column gap-3 p-1">
          <div className="d-flex align-items-center justify-content-between gap-3 border rounded p-3">
            <div>
              <div className="fw-medium">{d.respondAutomatically}</div>
              <p className="mb-0 mt-1 small text-body-secondary">
                {d.respondAutomaticallyHelp}
              </p>
            </div>
            <Switch
              checked={draft.respond_automatically}
              disabled={saving}
              onChange={(checked) => patch({ respond_automatically: checked })}
              aria-label={d.respondAutomaticallyAria}
            />
          </div>
          <ResponseSwitch
            label={d.pauseInvites}
            checked={draft.pause_invites}
            disabled={!draft.respond_automatically}
            onChange={(checked) => patch({ pause_invites: checked })}
          />
          <ResponseSwitch
            label={d.forceVerification}
            checked={draft.force_verification}
            disabled={!draft.respond_automatically}
            onChange={(checked) => patch({ force_verification: checked })}
          />
          <ResponseSwitch
            label={d.kickYoungAccounts}
            checked={draft.kick_young_accounts}
            disabled={!draft.respond_automatically}
            onChange={(checked) => patch({ kick_young_accounts: checked })}
          />
          <ResponseSwitch
            label={d.pauseInviteCrediting}
            checked={draft.pause_invite_crediting}
            disabled={!draft.respond_automatically}
            onChange={(checked) => patch({ pause_invite_crediting: checked })}
          />
        </div>
      </SectionCard>
      </MutedSection>

      <SectionCard level="secondary" header={d.incidentHistory}>
        {incidents.length === 0 ? (
          <p className="mb-0 small text-body-secondary p-1">
            {d.emptyIncidents}
          </p>
        ) : (
          <div className="table-responsive">
            <table className="table table-sm align-middle mb-0">
              <thead>
                <tr>
                  <th>{d.colStarted}</th>
                  <th>{d.colStatus}</th>
                  <th>{d.colJoins}</th>
                  <th>{d.colYoungPct}</th>
                  <th>{d.colPeakPerMin}</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((item, index) => (
                  <tr key={String(item.id ?? index)}>
                    <td className="small">
                      {String(item.started_at ?? item.start_time ?? "—")}
                    </td>
                    <td className="small">{String(item.status ?? "—")}</td>
                    <td className="small">
                      {String(item.total_joins ?? item.joins ?? "—")}
                    </td>
                    <td className="small">
                      {String(item.young_account_ratio ?? "—")}
                    </td>
                    <td className="small">
                      {String(item.peak_join_rate ?? "—")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      <PageActionFooter>
        <Button
          variant="primary"
          disabled={saving || !draft.enabled || !dirty}
          onClick={() => void save(guildId, draft)}
        >
          {saving ? d.saving : d.saveSettings}
        </Button>
      </PageActionFooter>
    </div>
  );
}

function ResponseSwitch({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="d-flex align-items-center justify-content-between gap-3 border rounded p-3">
      <div className="fw-medium">{label}</div>
      <Switch
        checked={checked}
        disabled={disabled}
        onChange={onChange}
        aria-label={label}
      />
    </div>
  );
}
