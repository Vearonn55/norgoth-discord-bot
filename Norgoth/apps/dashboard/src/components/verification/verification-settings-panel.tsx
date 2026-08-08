"use client";

import { useEffect } from "react";
import {
  CAlert,
  CCol,
  CFormInput,
  CFormLabel,
  CFormSelect,
  CRow,
  CSpinner,
} from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { browserApiUrl } from "@/lib/api";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useVerificationStore } from "@/stores/verification-store";

export function VerificationSettingsPanel() {
  const { guildId, resources, loading: guildLoading, error: guildError, reload } =
    useFirstGuild();

  const config = useVerificationStore((s) => s.config);
  const configured = useVerificationStore((s) => s.configured);
  const loading = useVerificationStore((s) => s.loading);
  const saving = useVerificationStore((s) => s.saving);
  const error = useVerificationStore((s) => s.error);
  const savedAt = useVerificationStore((s) => s.savedAt);
  const publishing = useVerificationStore((s) => s.publishing);
  const publishFeedback = useVerificationStore((s) => s.publishFeedback);
  const copied = useVerificationStore((s) => s.copied);
  const setConfig = useVerificationStore((s) => s.setConfig);
  const loadConfig = useVerificationStore((s) => s.loadConfig);
  const save = useVerificationStore((s) => s.save);
  const publishPanel = useVerificationStore((s) => s.publishPanel);
  const copyVerifyLink = useVerificationStore((s) => s.copyVerifyLink);

  useEffect(() => {
    if (!guildId) return;
    void loadConfig(guildId);
  }, [guildId, loadConfig]);

  if (guildLoading || loading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          <span>Loading verification settings…</span>
        </div>
      </Card>
    );
  }

  if (guildError || !guildId) {
    return (
      <Card>
        <div className="d-flex flex-column gap-3">
          <Badge variant="warning">Bot required</Badge>
          <p className="mb-0 text-body-secondary">{guildError}</p>
          <Button variant="secondary" onClick={() => void reload()}>
            Retry
          </Button>
        </div>
      </Card>
    );
  }

  const channels = resources?.channels ?? [];
  const roles = (resources?.roles ?? []).filter((role) => !role.managed);
  const verifyUrl = browserApiUrl(`/api/v1/oauth/discord/authorize/${guildId}`);

  return (
    <div className="d-flex flex-column gap-4">
      <div className="d-flex align-items-center gap-2">
        {resources && <Badge variant="success">{resources.guild_name}</Badge>}
        <Badge variant={configured ? "success" : "warning"}>
          {configured ? "Verification configured" : "Not configured yet"}
        </Badge>
      </div>

      <Card>
        <div className="d-flex flex-column gap-4">
          <h2 className="h5 mb-0">Channels</h2>

          <CRow className="g-3">
            <CCol md={6}>
              <Select
                label="Verification channel"
                value={config.verification_channel_id}
                options={channels.map((c) => ({ value: c.id, label: `#${c.name}` }))}
                onChange={(value) =>
                  setConfig((c) => ({ ...c, verification_channel_id: value }))
                }
              />
            </CCol>
            <CCol md={6}>
              <Select
                label="Log channel"
                value={config.log_channel_id}
                options={channels.map((c) => ({ value: c.id, label: `#${c.name}` }))}
                onChange={(value) =>
                  setConfig((c) => ({ ...c, log_channel_id: value }))
                }
              />
            </CCol>
          </CRow>

          <h2 className="h5 mb-0">Roles</h2>

          <CRow className="g-3">
            <CCol md={4}>
              <Select
                label="Verified role"
                value={config.verified_role_id}
                options={roles.map((r) => ({ value: r.id, label: `@${r.name}` }))}
                onChange={(value) =>
                  setConfig((c) => ({ ...c, verified_role_id: value }))
                }
              />
            </CCol>
            <CCol md={4}>
              <Select
                label="Unverified role"
                value={config.unverified_role_id}
                options={roles.map((r) => ({ value: r.id, label: `@${r.name}` }))}
                onChange={(value) =>
                  setConfig((c) => ({ ...c, unverified_role_id: value }))
                }
              />
            </CCol>
            <CCol md={4}>
              <Select
                label="Member role"
                value={config.member_role_id}
                options={roles.map((r) => ({ value: r.id, label: `@${r.name}` }))}
                onChange={(value) =>
                  setConfig((c) => ({ ...c, member_role_id: value }))
                }
              />
            </CCol>
          </CRow>

          <h2 className="h5 mb-0">Policy</h2>

          <CRow className="g-3">
            <CCol md={6}>
              <CFormLabel>Minimum account age (days)</CFormLabel>
              <CFormInput
                type="number"
                min={0}
                max={3650}
                value={config.minimum_account_age_days}
                onChange={(event) =>
                  setConfig((c) => ({
                    ...c,
                    minimum_account_age_days: Number(event.target.value) || 0,
                  }))
                }
              />
            </CCol>
          </CRow>

          <Toggle
            label="Verification enabled"
            description="Turn the whole verification flow on or off."
            checked={config.enabled}
            onChange={(v) => setConfig((c) => ({ ...c, enabled: v }))}
          />
          <Toggle
            label="Deny VPN / proxy connections"
            description="Reject members connecting through a VPN or proxy (proxycheck.io)."
            checked={config.deny_vpn_or_proxy}
            onChange={(v) => setConfig((c) => ({ ...c, deny_vpn_or_proxy: v }))}
          />
          <Toggle
            label="Deny shared IPs (alt accounts)"
            description="Reject members whose IP already verified another account."
            checked={config.deny_shared_ip}
            onChange={(v) => setConfig((c) => ({ ...c, deny_shared_ip: v }))}
          />
        </div>
      </Card>

      <Card>
        <div className="d-flex flex-column gap-3">
          <h2 className="h5 mb-0">Verification link & Discord panel</h2>
          <p className="mb-0 text-body-secondary small">
            Members open this URL in a browser to complete Discord OAuth.
            Requires{" "}
            <code>
              NORGOTH_DISCORD_CLIENT_ID / CLIENT_SECRET / REDIRECT_URI
            </code>{" "}
            in <code>Norgoth/.env</code> (redirect must match the Discord
            Developer Portal).
          </p>
          <code className="d-block border rounded p-3 small text-success text-break">
            {verifyUrl}
          </code>
          <div className="d-flex flex-wrap align-items-center gap-2">
            <Button
              variant="secondary"
              onClick={() => void copyVerifyLink(verifyUrl)}
            >
              {copied ? "Copied" : "Copy link"}
            </Button>
            <a
              href={verifyUrl}
              target="_blank"
              rel="noreferrer"
              className="d-inline-flex"
            >
              <Button variant="secondary">Open in browser</Button>
            </a>
            <Button
              variant="primary"
              onClick={() => void publishPanel(guildId)}
              disabled={publishing || !config.verification_channel_id}
            >
              {publishing ? "Publishing…" : "Publish Discord verify panel"}
            </Button>
          </div>
          {publishFeedback && (
            <CAlert color="secondary" className="mb-0 py-2">
              {publishFeedback}
            </CAlert>
          )}
        </div>
      </Card>

      <div className="d-flex align-items-center gap-3">
        <Button
          variant="primary"
          onClick={() => void save(guildId)}
          disabled={saving}
        >
          {saving ? "Saving…" : "Save Verification Settings"}
        </Button>

        {savedAt && (
          <span className="small text-success">Saved at {savedAt}</span>
        )}

        {error && (
          <CAlert color="danger" className="mb-0 py-2">
            {error}
          </CAlert>
        )}
      </div>
    </div>
  );
}

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <CFormLabel>{label}</CFormLabel>
      <CFormSelect
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Select…</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </CFormSelect>
    </div>
  );
}

function Toggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="d-flex align-items-center justify-content-between gap-3 border rounded p-3">
      <div>
        <div className="fw-medium">{label}</div>
        <p className="mb-0 mt-1 small text-body-secondary">{description}</p>
      </div>

      <Switch checked={checked} onChange={onChange} aria-label={label} />
    </div>
  );
}
