"use client";

import { useEffect } from "react";
import { cilPeople } from "@coreui/icons";
import { CAlert } from "@coreui/react";
import { PageHeader } from "@/components/layout/page-header";
import { ManagingGuildLabel } from "@/components/layout/managing-guild-label";
import { Icon } from "@/components/ui/icon";
import { MutedSection } from "@/components/ui/feature-muting";
import { VerificationDetectorsPanel } from "@/components/verification/verification-detectors-panel";
import { VerificationLogsPanel } from "@/components/verification/verification-logs-panel";
import { useFeatureInfo } from "@/lib/feature-info";
import { useLocaleDict } from "@/lib/locale-dict";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useVerificationStore } from "@/stores/verification-store";

/**
 * Member Verification page body. Owns the page-level master enable/disable
 * switch (in the header, always interactive) and mutes the configuration body
 * when verification is disabled. The master state is the single authoritative
 * `guild_settings.enabled` flag, transitioned atomically backend-side.
 */
export function MemberVerificationView() {
  const { guildId } = useFirstGuild();
  const dict = useLocaleDict();
  const d = dict.verificationPage;
  const info = useFeatureInfo("memberVerification");
  const config = useVerificationStore((s) => s.config);
  const loading = useVerificationStore((s) => s.loading);
  const error = useVerificationStore((s) => s.error);
  const settingsModalOpen = useVerificationStore((s) => s.settingsModalOpen);
  const publishFeedback = useVerificationStore((s) => s.publishFeedback);
  const setError = useVerificationStore((s) => s.setError);
  const loadConfig = useVerificationStore((s) => s.loadConfig);
  const applyVerificationState = useVerificationStore(
    (s) => s.applyVerificationState,
  );

  useEffect(() => {
    if (guildId) void loadConfig(guildId);
  }, [guildId, loadConfig]);

  const setupState = config.setup_state ?? "not_configured";
  const needsBindings =
    setupState === "not_configured" || setupState === "incomplete";

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={info?.title ?? "Member Verification"}
        icon={<Icon icon={cilPeople} size="xl" />}
        category="community"
        description={<ManagingGuildLabel />}
        infoKey="memberVerification"
        masterToggle={{
          enabled: config.enabled,
          loading: loading || !guildId,
          label: "Verification",
          showLabel: false,
          onChange: async (checked) => {
            if (!guildId) return;
            const result = await applyVerificationState(guildId, {
              enabled: checked,
            });
            if (!result.ok && result.error) {
              setError(result.error);
            }
          },
        }}
      />

      {error && !settingsModalOpen && (
        <CAlert color="danger" className="mb-0">
          {error}
        </CAlert>
      )}

      {publishFeedback && !error && !settingsModalOpen ? (
        <CAlert color="success" className="mb-0">
          {publishFeedback}
        </CAlert>
      ) : null}

      {needsBindings && (
        <CAlert color="warning" className="mb-0">
          {d.bindingsWarning}
        </CAlert>
      )}

      <MutedSection
        enabled={config.enabled}
        className="d-flex flex-column gap-4"
      >
        <VerificationDetectorsPanel />
        <VerificationLogsPanel />
      </MutedSection>
    </div>
  );
}
