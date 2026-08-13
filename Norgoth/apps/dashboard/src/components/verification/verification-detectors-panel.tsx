"use client";

import { useState } from "react";
import { cilPeople, cilSettings, cilShieldAlt } from "@coreui/icons";
import { CFormLabel, CFormSelect } from "@coreui/react";
import { MiniFeatureCard } from "@/components/ui/mini-feature-card";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { VerificationSettingsModal } from "@/components/verification/verification-settings-modal";
import { useFirstGuild } from "@/lib/use-first-guild";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";
import { useVerificationStore, type RiskAction } from "@/stores/verification-store";

type DetectorKey = "vpn" | "shared_ip";

/**
 * Two mini feature cards (VPN/Proxy, Shared IP) shown above the Verification
 * Log. Each card owns its enable/disable switch (persisted instantly) and opens
 * a modal to configure the detection-result action (Deny vs. Manual Review).
 * Disabled detectors have no effect on verification — enforced backend-side.
 */
export function VerificationDetectorsPanel() {
  const dict = useLocaleDict();
  const d = dict.verificationPage;
  const { guildId } = useFirstGuild();
  const config = useVerificationStore((s) => s.config);
  const loading = useVerificationStore((s) => s.loading);
  const patchDetectors = useVerificationStore((s) => s.patchDetectors);
  const applyVerificationState = useVerificationStore(
    (s) => s.applyVerificationState
  );

  const [openKey, setOpenKey] = useState<DetectorKey | null>(null);
  const [draftAction, setDraftAction] = useState<RiskAction>("deny");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);

  if (!guildId) return null;

  const actionLabels: Record<RiskAction, string> = {
    deny: d.actionDeny,
    manual_review: d.actionManualReview,
  };

  const detectors: Record<
    DetectorKey,
    {
      title: string;
      icon: string[];
      baseDescription: string;
      enabled: boolean;
      action: RiskAction;
    }
  > = {
    vpn: {
      title: d.vpnTitle,
      icon: cilShieldAlt,
      baseDescription: d.vpnDesc,
      enabled: config.deny_vpn_or_proxy,
      action: config.vpn_or_proxy_action,
    },
    shared_ip: {
      title: d.sharedIpTitle,
      icon: cilPeople,
      baseDescription: d.sharedIpDesc,
      enabled: config.deny_shared_ip,
      action: config.shared_ip_action,
    },
  };

  async function toggle(key: DetectorKey, checked: boolean) {
    setError(null);
    // Enabling/disabling a detector runs through the authoritative state
    // machine so turning the last one off also disables the master switch.
    const patch =
      key === "vpn"
        ? { deny_vpn_or_proxy: checked }
        : { deny_shared_ip: checked };
    const result = await applyVerificationState(guildId!, patch);
    if (!result.ok) setError(result.error ?? d.updateFailed);
  }

  function openModal(key: DetectorKey) {
    setError(null);
    setDraftAction(detectors[key].action);
    setOpenKey(key);
  }

  async function saveModal() {
    if (!openKey) return;
    setSaving(true);
    setError(null);
    const patch =
      openKey === "vpn"
        ? { vpn_or_proxy_action: draftAction }
        : { shared_ip_action: draftAction };
    const result = await patchDetectors(guildId!, patch);
    setSaving(false);
    if (result.ok) setOpenKey(null);
    else setError(result.error ?? d.saveFailed);
  }

  const activeDetector = openKey ? detectors[openKey] : null;

  return (
    <div className="d-flex flex-column gap-3">
      <MiniFeatureCard
        icon={cilSettings}
        name={d.detectorsSettingsCard}
        description={d.detectorsSettingsDesc}
        category="community"
        onClick={() => setSettingsOpen(true)}
      />

      <div className="row g-3">
        {(["vpn", "shared_ip"] as DetectorKey[]).map((key) => {
          const detector = detectors[key];
          const description = detector.enabled
            ? `${detector.baseDescription}${formatDict(d.actionSuffix, {
                action: actionLabels[detector.action],
              })}`
            : detector.baseDescription;
          return (
            <div className="col-md-6" key={key}>
              <MiniFeatureCard
                icon={detector.icon}
                name={detector.title}
                description={description}
                category="community"
                enabled={detector.enabled}
                toggleDisabled={loading}
                onToggle={(checked) => void toggle(key, checked)}
                onClick={() => openModal(key)}
              />
            </div>
          );
        })}
      </div>

      <FeatureConfigurationModal
        visible={openKey !== null}
        title={activeDetector?.title ?? ""}
        icon={activeDetector?.icon}
        category="community"
        description={d.detectorModalDesc}
        saving={saving}
        error={error}
        onClose={() => setOpenKey(null)}
        onSave={saveModal}
        saveLabel={d.save}
      >
        {activeDetector ? (
          <div className="d-flex flex-column gap-3">
            <div>
              <CFormLabel>{d.detectionResultAction}</CFormLabel>
              <CFormSelect
                value={draftAction}
                onChange={(event) =>
                  setDraftAction(event.target.value as RiskAction)
                }
              >
                <option value="deny">{d.actionDeny}</option>
                <option value="manual_review">{d.actionManualReview}</option>
              </CFormSelect>
              <p className="small text-body-secondary mt-1 mb-0">
                {draftAction === "deny"
                  ? d.detectorHelpDeny
                  : d.detectorHelpManual}
              </p>
            </div>
          </div>
        ) : null}
      </FeatureConfigurationModal>

      <VerificationSettingsModal
        visible={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
    </div>
  );
}
