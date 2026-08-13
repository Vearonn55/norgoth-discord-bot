"use client";

import { useMemo, useState } from "react";
import { CNav, CNavItem, CNavLink } from "@coreui/react";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { Button } from "@/components/ui/button";
import { VerificationSettingsForm } from "@/components/verification/verification-settings-form";
import { HighRiskServersSection } from "@/components/verification/high-risk-servers-section";
import { WhitelistedUsersSection } from "@/components/verification/whitelisted-users-section";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useLocaleDict } from "@/lib/locale-dict";

type VerificationSettingsModalProps = {
  visible: boolean;
  onClose: () => void;
};

type Section = "general" | "high-risk" | "whitelist";

/**
 * Verification Settings popout. Replaces the previously hidden standalone
 * Guild Configuration page: opens on the Member Verification page and reuses
 * the same settings form. Save is owned by the General form; the footer only
 * closes. High-risk and whitelist sections own their own persistence.
 */
export function VerificationSettingsModal({
  visible,
  onClose,
}: VerificationSettingsModalProps) {
  const dict = useLocaleDict();
  const d = dict.verificationPage;
  const { guildId } = useFirstGuild();
  const [section, setSection] = useState<Section>("general");

  const sections = useMemo(
    () =>
      [
        { id: "general" as const, label: d.tabGeneral },
        { id: "high-risk" as const, label: d.tabHighRisk },
        { id: "whitelist" as const, label: d.tabWhitelist },
      ] satisfies { id: Section; label: string }[],
    [d.tabGeneral, d.tabHighRisk, d.tabWhitelist],
  );

  return (
    <FeatureConfigurationModal
      visible={visible}
      onClose={onClose}
      title={d.settingsModalTitle}
      description={d.settingsModalDesc}
      category="community"
      size="xl"
      footer={
        <Button variant="secondary" onClick={onClose}>
          {d.close}
        </Button>
      }
    >
      <CNav variant="tabs" className="mb-4">
        {sections.map((item) => (
          <CNavItem key={item.id}>
            <CNavLink
              active={section === item.id}
              onClick={() => setSection(item.id)}
              style={{ cursor: "pointer" }}
            >
              {item.label}
            </CNavLink>
          </CNavItem>
        ))}
      </CNav>

      {section === "general" ? <VerificationSettingsForm /> : null}
      {section === "high-risk" && guildId ? (
        <HighRiskServersSection guildId={guildId} />
      ) : null}
      {section === "whitelist" && guildId ? (
        <WhitelistedUsersSection guildId={guildId} />
      ) : null}
    </FeatureConfigurationModal>
  );
}
