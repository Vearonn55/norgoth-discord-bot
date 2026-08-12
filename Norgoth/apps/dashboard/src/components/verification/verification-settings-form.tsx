"use client";

import { useEffect } from "react";
import {
  CAlert,
  CCol,
  CFormLabel,
  CFormSelect,
  CRow,
  CSpinner,
} from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { NumberInput } from "@/components/ui/number-input";
import { browserApiUrl } from "@/lib/api";
import { useFirstGuild } from "@/lib/use-first-guild";
import {
  canPublishOrCopy,
  useVerificationStore,
} from "@/stores/verification-store";

/**
 * Self-contained Verification (Guild Configuration) settings form. Handles its
 * own guild/config loading and Save action via the verification store, so it
 * can be dropped into either a standalone page or a modal without prop wiring.
 */
export function VerificationSettingsForm() {
  const {
    guildId,
    resources,
    loading: guildLoading,
    error: guildError,
    reload,
    selectedGuild,
  } = useFirstGuild();

  const config = useVerificationStore((s) => s.config);
  const configured = useVerificationStore((s) => s.configured);
  const loading = useVerificationStore((s) => s.loading);
  const saving = useVerificationStore((s) => s.saving);
  const validating = useVerificationStore((s) => s.validating);
  const error = useVerificationStore((s) => s.error);
  const savedAt = useVerificationStore((s) => s.savedAt);
  const publishing = useVerificationStore((s) => s.publishing);
  const publishFeedback = useVerificationStore((s) => s.publishFeedback);
  const copied = useVerificationStore((s) => s.copied);
  const setConfig = useVerificationStore((s) => s.setConfig);
  const loadConfig = useVerificationStore((s) => s.loadConfig);
  const save = useVerificationStore((s) => s.save);
  const validateDiscord = useVerificationStore((s) => s.validateDiscord);
  const publishPanel = useVerificationStore((s) => s.publishPanel);
  const copyVerifyLink = useVerificationStore((s) => s.copyVerifyLink);

  useEffect(() => {
    if (!guildId) return;
    void loadConfig(guildId);
  }, [guildId, loadConfig]);

  if (guildLoading || loading) {
    return (
      <div className="d-flex align-items-center gap-2 text-body-secondary">
        <CSpinner size="sm" />
        <span>Loading verification settings…</span>
      </div>
    );
  }

  if (guildError || !guildId) {
    return (
      <div className="d-flex flex-column gap-3">
        <Badge variant="warning">Bot required</Badge>
        <p className="mb-0 text-body-secondary">{guildError}</p>
        <Button variant="secondary" onClick={() => void reload()}>
          Retry
        </Button>
      </div>
    );
  }

  const channels = resources?.channels ?? [];
  const roles = (resources?.roles ?? []).filter((role) => !role.managed);
  const verifyUrl = browserApiUrl(`/api/v1/oauth/discord/authorize/${guildId}`);
  const setupState = config.setup_state ?? "not_configured";
  const linkReady = canPublishOrCopy(config);
  const missing = config.missing_bindings ?? [];

  const setupBadgeVariant =
    setupState === "active"
      ? "success"
      : setupState === "disabled"
        ? "warning"
        : "warning";

  return (
    <div className="d-flex flex-column gap-4">
      <div className="d-flex flex-wrap align-items-center gap-2">
        {selectedGuild?.icon_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={selectedGuild.icon_url}
            alt=""
            width={28}
            height={28}
            className="rounded-circle"
          />
        ) : null}
        {resources && <Badge variant="success">{resources.guild_name}</Badge>}
        <Badge variant={setupBadgeVariant}>
          {setupState === "active"
            ? "Verification active"
            : setupState === "disabled"
              ? "Configured · disabled"
              : setupState === "incomplete"
                ? "Setup incomplete"
                : setupState === "degraded"
                  ? "Discord resources degraded"
                  : configured
                    ? "Verification configured"
                    : "Not configured yet"}
        </Badge>
      </div>

      {(setupState === "not_configured" || setupState === "incomplete") && (
        <CAlert color="info" className="mb-0 py-2">
          Create or reuse Discord channels and roles, then save them here. Public
          verification and Discord panel publish stay locked until required
          bindings are saved
          {missing.length ? ` (missing: ${missing.join(", ")})` : ""}.
        </CAlert>
      )}

      <Card>
        <div className="d-flex flex-column gap-4">
          <h2 className="h5 mb-0">Channels</h2>

          <CRow className="g-3">
            <CCol md={6}>
              <Select
                label="Verification channel"
                value={config.verification_channel_id}
                options={channels.map((c) => ({
                  value: c.id,
                  label: `#${c.name}`,
                }))}
                onChange={(value) =>
                  setConfig((c) => ({ ...c, verification_channel_id: value }))
                }
              />
            </CCol>
            <CCol md={6}>
              <Select
                label="Log channel"
                value={config.log_channel_id}
                options={channels.map((c) => ({
                  value: c.id,
                  label: `#${c.name}`,
                }))}
                onChange={(value) =>
                  setConfig((c) => ({ ...c, log_channel_id: value }))
                }
              />
            </CCol>
          </CRow>

          <h2 className="h5 mb-0">Roles</h2>

          <CRow className="g-3">
            <CCol md={6}>
              <Select
                label="Unverified role"
                value={config.unverified_role_id}
                options={roles.map((r) => ({
                  value: r.id,
                  label: `@${r.name}`,
                }))}
                onChange={(value) =>
                  setConfig((c) => ({ ...c, unverified_role_id: value }))
                }
              />
            </CCol>
            <CCol md={6}>
              <Select
                label="Base member role"
                value={config.member_role_id}
                options={roles.map((r) => ({
                  value: r.id,
                  label: `@${r.name}`,
                }))}
                onChange={(value) =>
                  setConfig((c) => ({ ...c, member_role_id: value }))
                }
              />
            </CCol>
          </CRow>
          <p className="mb-0 small text-body-secondary">
            On successful verification the Unverified role is removed and the
            Base member role is granted. NorBot does not create these Discord
            resources — select existing ones.
          </p>

          <CRow className="g-3">
            <CCol md={6}>
              <Select
                label="Manual review role (optional)"
                value={config.manual_review_role_id}
                options={roles.map((r) => ({
                  value: r.id,
                  label: `@${r.name}`,
                }))}
                onChange={(value) =>
                  setConfig((c) => ({ ...c, manual_review_role_id: value }))
                }
              />
              <p className="mb-0 mt-1 small text-body-secondary">
                Pinged in the log channel when a member is routed to Manual
                Review (e.g. a High Risk Server match).
              </p>
            </CCol>
          </CRow>

          <h2 className="h5 mb-0">Policy</h2>

          <CRow className="g-3">
            <CCol md={6}>
              <CFormLabel>Minimum account age (days)</CFormLabel>
              <NumberInput
                value={config.minimum_account_age_days}
                defaultValue={0}
                min={0}
                max={3650}
                step={1}
                aria-label="Minimum account age in days"
                onCommit={(next) =>
                  setConfig((c) => ({
                    ...c,
                    minimum_account_age_days: next,
                  }))
                }
              />
            </CCol>
          </CRow>

          <p className="mb-0 small text-body-secondary">
            The verification master switch lives in the page header. VPN / Proxy
            and Shared IP detection are configured from the mini cards on the
            Member Verification page.
          </p>
        </div>
      </Card>

      <Card>
        <div className="d-flex flex-column gap-3">
          <h2 className="h5 mb-0">Verification link & Discord panel</h2>
          <p className="mb-0 text-body-secondary small">
            Members open this URL in a browser to complete Discord OAuth.
            Requires Discord OAuth env vars and an active setup (channels +
            roles saved, master enabled).
          </p>
          <code className="d-block border rounded p-3 small text-success text-break">
            {verifyUrl}
          </code>
          <div className="d-flex flex-wrap align-items-center gap-2">
            <Button
              variant="secondary"
              disabled={!linkReady}
              onClick={() => void copyVerifyLink(verifyUrl)}
            >
              {copied ? "Copied" : "Copy link"}
            </Button>
            {linkReady ? (
              <a
                href={verifyUrl}
                target="_blank"
                rel="noreferrer"
                className="d-inline-flex"
              >
                <Button variant="secondary">Open in browser</Button>
              </a>
            ) : (
              <Button variant="secondary" disabled>
                Open in browser
              </Button>
            )}
            <Button
              variant="primary"
              onClick={() => void publishPanel(guildId)}
              disabled={publishing || !linkReady}
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

      <div className="d-flex flex-wrap align-items-center gap-3">
        <Button
          variant="primary"
          onClick={() => void save(guildId)}
          disabled={saving}
        >
          {saving ? "Saving…" : "Save Verification Settings"}
        </Button>
        <Button
          variant="secondary"
          onClick={() => void validateDiscord(guildId)}
          disabled={validating || !hasLocalRequired(config)}
        >
          {validating ? "Validating…" : "Validate Discord"}
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

function hasLocalRequired(config: {
  verification_channel_id: string;
  log_channel_id: string;
  unverified_role_id: string;
  member_role_id: string;
}): boolean {
  return Boolean(
    config.verification_channel_id &&
      config.log_channel_id &&
      config.unverified_role_id &&
      config.member_role_id
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
