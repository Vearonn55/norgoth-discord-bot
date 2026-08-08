"use client";

import { useEffect, useState } from "react";
import {
  CFormInput,
  CFormLabel,
  CSpinner,
} from "@coreui/react";
import { SectionCard } from "@/components/ui/section-card";
import { ChannelSelect } from "@/components/ui/channel-select";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { MutedSection } from "@/components/ui/feature-muting";
import { PageHeader } from "@/components/layout/page-header";
import { PageActionFooter } from "@/components/layout/page-action-footer";
import { useFirstGuild } from "@/stores/guild-store";
import { useRaidStore, type RaidConfig } from "@/stores/raid-store";
import { Icon } from "@/components/ui/icon";
import { cilShieldAlt } from "@coreui/icons";

export function RaidProtectionPanel() {
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
        <CSpinner size="sm" /> Loading raid protection…
      </div>
    );
  }

  if (!guildId) {
    return <p className="text-body-secondary">Select a server first.</p>;
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
        title="Raid Protection"
        category="security"
        icon={<Icon icon={cilShieldAlt} size="xl" />}
        description="Detect rapid joins and young-account floods, then respond automatically when configured."
        masterToggle={{
          enabled: draft.enabled,
          onChange: (checked) => void setEnabledAndSave(checked),
          loading: saving,
        }}
      />

      {error ? <p className="text-danger">{error}</p> : null}

      {draft.active_incident ? (
        <div className="alert alert-warning mb-0">
          Active raid response in progress. Automatic defenses remain engaged
          until the response window ends.
        </div>
      ) : null}

      <MutedSection enabled={draft.enabled} className="d-flex flex-column gap-4">
      <SectionCard level="primary" category="security" header="Raid Detection">
        <div className="d-flex flex-column gap-3 p-1">
          <div>
            <CFormLabel>Alert Channel</CFormLabel>
            <ChannelSelect
              channels={resources?.channels ?? []}
              value={draft.alert_channel_id ?? ""}
              onChange={(v) => patch({ alert_channel_id: v || null })}
            />
          </div>
          <div style={{ maxWidth: 420 }}>
            <div className="d-flex align-items-center justify-content-between">
              <CFormLabel className="mb-0">Joins Per Minute</CFormLabel>
              <span className="fw-semibold">{draft.joins_per_minute}</span>
            </div>
            <Slider
              min={2}
              max={100}
              value={draft.joins_per_minute}
              onChange={(value) => patch({ joins_per_minute: value })}
              aria-label="Joins per minute"
            />
          </div>
          <div style={{ maxWidth: 420 }}>
            <div className="d-flex align-items-center justify-content-between">
              <CFormLabel className="mb-0">Young Account Age (days)</CFormLabel>
              <span className="fw-semibold">
                {draft.young_account_age_days}
              </span>
            </div>
            <Slider
              min={1}
              max={90}
              value={draft.young_account_age_days}
              onChange={(value) => patch({ young_account_age_days: value })}
              aria-label="Young account age in days"
            />
          </div>
          <div style={{ maxWidth: 420 }}>
            <div className="d-flex align-items-center justify-content-between">
              <CFormLabel className="mb-0">Young Account Ratio (%)</CFormLabel>
              <span className="fw-semibold">{draft.young_account_ratio}</span>
            </div>
            <Slider
              min={0}
              max={100}
              value={draft.young_account_ratio}
              onChange={(value) => patch({ young_account_ratio: value })}
              aria-label="Young account ratio percent"
            />
          </div>
          <div>
            <CFormLabel>Response Duration (minutes)</CFormLabel>
            <CFormInput
              type="number"
              min={1}
              max={1440}
              value={draft.response_duration_minutes}
              onChange={(e) =>
                patch({ response_duration_minutes: Number(e.target.value) })
              }
            />
          </div>
        </div>
      </SectionCard>

      <SectionCard level="primary" category="security" header="Automatic Response">
        <div className="d-flex flex-column gap-3 p-1">
          <div className="d-flex align-items-center justify-content-between gap-3 border rounded p-3">
            <div>
              <div className="fw-medium">Respond Automatically</div>
              <p className="mb-0 mt-1 small text-body-secondary">
                When enabled, Norgoth applies the responses below the moment a
                raid is detected.
              </p>
            </div>
            <Switch
              checked={draft.respond_automatically}
              disabled={saving}
              onChange={(checked) => patch({ respond_automatically: checked })}
              aria-label="Respond automatically"
            />
          </div>
          <ResponseSwitch
            label="Pause Invites"
            checked={draft.pause_invites}
            disabled={!draft.respond_automatically}
            onChange={(checked) => patch({ pause_invites: checked })}
          />
          <ResponseSwitch
            label="Force Verification (raise Discord verification level)"
            checked={draft.force_verification}
            disabled={!draft.respond_automatically}
            onChange={(checked) => patch({ force_verification: checked })}
          />
          <ResponseSwitch
            label="Kick Young Accounts"
            checked={draft.kick_young_accounts}
            disabled={!draft.respond_automatically}
            onChange={(checked) => patch({ kick_young_accounts: checked })}
          />
          <ResponseSwitch
            label="Pause Invite Crediting"
            checked={draft.pause_invite_crediting}
            disabled={!draft.respond_automatically}
            onChange={(checked) => patch({ pause_invite_crediting: checked })}
          />
        </div>
      </SectionCard>
      </MutedSection>

      <SectionCard level="secondary" header="Incident History">
        {incidents.length === 0 ? (
          <p className="mb-0 small text-body-secondary p-1">
            No raid incidents recorded yet.
          </p>
        ) : (
          <div className="table-responsive">
            <table className="table table-sm align-middle mb-0">
              <thead>
                <tr>
                  <th>Started</th>
                  <th>Status</th>
                  <th>Joins</th>
                  <th>Young %</th>
                  <th>Peak / min</th>
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
          {saving ? "Saving…" : "Save Settings"}
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
