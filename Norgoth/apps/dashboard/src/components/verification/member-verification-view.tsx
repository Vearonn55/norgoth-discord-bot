"use client";

import { useEffect } from "react";
import { cilPeople } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { Icon } from "@/components/ui/icon";
import { MutedSection } from "@/components/ui/feature-muting";
import { VerificationDetectorsPanel } from "@/components/verification/verification-detectors-panel";
import { VerificationLogsPanel } from "@/components/verification/verification-logs-panel";
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
  const config = useVerificationStore((s) => s.config);
  const loading = useVerificationStore((s) => s.loading);
  const loadConfig = useVerificationStore((s) => s.loadConfig);
  const applyVerificationState = useVerificationStore(
    (s) => s.applyVerificationState
  );

  useEffect(() => {
    if (guildId) void loadConfig(guildId);
  }, [guildId, loadConfig]);

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Member Verification"
        icon={<Icon icon={cilPeople} size="xl" />}
        category="community"
        description="Verification outcomes for members joining this server."
        infoKey="memberVerification"
        masterToggle={{
          enabled: config.enabled,
          loading: loading || !guildId,
          label: "Verification",
          onChange: (checked) => {
            if (guildId)
              void applyVerificationState(guildId, { enabled: checked });
          },
        }}
      />

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
