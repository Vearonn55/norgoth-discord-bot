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
import { formatDict, useLocaleDict } from "@/lib/locale-dict";
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
  const dict = useLocaleDict();
  const d = dict.verificationPage;
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
  const validating = useVerificationStore((s) => s.validating);
  const savedAt = useVerificationStore((s) => s.savedAt);
  const copied = useVerificationStore((s) => s.copied);
  const setConfig = useVerificationStore((s) => s.setConfig);
  const loadConfig = useVerificationStore((s) => s.loadConfig);
  const validateDiscord = useVerificationStore((s) => s.validateDiscord);
  const copyVerifyLink = useVerificationStore((s) => s.copyVerifyLink);

  useEffect(() => {
    if (!guildId) return;
    void loadConfig(guildId);
  }, [guildId, loadConfig]);

  if (guildLoading || loading) {
    return (
      <div className="d-flex align-items-center gap-2 text-body-secondary">
        <CSpinner size="sm" />
        <span>{d.loadingSettings}</span>
      </div>
    );
  }

  if (guildError || !guildId) {
    return (
      <div className="d-flex flex-column gap-3">
        <Badge variant="warning">{d.botRequired}</Badge>
        <p className="mb-0 text-body-secondary">{guildError}</p>
        <Button variant="secondary" onClick={() => void reload()}>
          {d.retry}
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

  const setupLabel =
    setupState === "active"
      ? d.setupActive
      : setupState === "disabled"
        ? d.setupDisabled
        : setupState === "incomplete"
          ? d.setupIncomplete
          : setupState === "degraded"
            ? d.setupDegraded
            : configured
              ? d.setupConfigured
              : d.setupNotConfigured;

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
        <Badge variant={setupBadgeVariant}>{setupLabel}</Badge>
      </div>

      {(setupState === "not_configured" || setupState === "incomplete") && (
        <CAlert color="info" className="mb-0 py-2">
          {formatDict(d.setupAlert, {
            missing: missing.length
              ? formatDict(d.missingSuffix, { list: missing.join(", ") })
              : "",
          })}
        </CAlert>
      )}

      <Card>
        <div className="d-flex flex-column gap-4">
          <h2 className="h5 mb-0">{d.channels}</h2>

          <CRow className="g-3">
            <CCol md={6}>
              <Select
                label={d.verificationChannel}
                selectPlaceholder={d.selectPlaceholder}
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
          </CRow>

          <h2 className="h5 mb-0">{d.roles}</h2>

          <CRow className="g-3">
            <CCol md={6}>
              <Select
                label={d.unverifiedRole}
                selectPlaceholder={d.selectPlaceholder}
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
                label={d.memberRole}
                selectPlaceholder={d.selectPlaceholder}
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
          <p className="mb-0 small text-body-secondary">{d.rolesHelp}</p>

          <CRow className="g-3">
            <CCol md={6}>
              <Select
                label={d.manualReviewRole}
                selectPlaceholder={d.selectPlaceholder}
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
                {d.manualReviewRoleHelp}
              </p>
            </CCol>
          </CRow>

          <h2 className="h5 mb-0">{d.policy}</h2>

          <CRow className="g-3">
            <CCol md={6}>
              <CFormLabel>{d.minAccountAge}</CFormLabel>
              <NumberInput
                value={config.minimum_account_age_days}
                defaultValue={0}
                min={0}
                max={3650}
                step={1}
                aria-label={d.minAccountAgeAria}
                onCommit={(next) =>
                  setConfig((c) => ({
                    ...c,
                    minimum_account_age_days: next,
                  }))
                }
              />
            </CCol>
          </CRow>

          <p className="mb-0 small text-body-secondary">{d.policyNote}</p>
        </div>
      </Card>

      <Card>
        <div className="d-flex flex-column gap-3">
          <h2 className="h5 mb-0">{d.linkPanelTitle}</h2>
          <p className="mb-0 text-body-secondary small">{d.linkPanelDesc}</p>
          <code className="d-block border rounded p-3 small text-success text-break">
            {verifyUrl}
          </code>
          <div className="d-flex flex-wrap align-items-center gap-2">
            <Button
              variant="secondary"
              disabled={!linkReady}
              onClick={() => void copyVerifyLink(verifyUrl)}
            >
              {copied ? d.copied : d.copyLink}
            </Button>
            {linkReady ? (
              <a
                href={verifyUrl}
                target="_blank"
                rel="noreferrer"
                className="d-inline-flex"
              >
                <Button variant="secondary">{d.openInBrowser}</Button>
              </a>
            ) : (
              <Button variant="secondary" disabled>
                {d.openInBrowser}
              </Button>
            )}
          </div>
        </div>
      </Card>

      <div className="d-flex flex-wrap align-items-center gap-3">
        <Button
          variant="secondary"
          onClick={() => void validateDiscord(guildId)}
          disabled={validating || !hasLocalRequired(config)}
        >
          {validating ? d.validating : d.validateDiscord}
        </Button>

        {savedAt && (
          <span className="small text-success">
            {formatDict(d.savedAt, { time: savedAt })}
          </span>
        )}
      </div>
    </div>
  );
}

function hasLocalRequired(config: {
  verification_channel_id: string;
  unverified_role_id: string;
  member_role_id: string;
}): boolean {
  return Boolean(
    config.verification_channel_id &&
      config.unverified_role_id &&
      config.member_role_id
  );
}

function Select({
  label,
  value,
  options,
  onChange,
  selectPlaceholder,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  selectPlaceholder: string;
}) {
  return (
    <div>
      <CFormLabel>{label}</CFormLabel>
      <CFormSelect
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{selectPlaceholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </CFormSelect>
    </div>
  );
}
