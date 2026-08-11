"use client";

import { useState } from "react";
import { CNav, CNavItem, CNavLink } from "@coreui/react";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { Button } from "@/components/ui/button";
import { VerificationSettingsForm } from "@/components/verification/verification-settings-form";
import { HighRiskServersSection } from "@/components/verification/high-risk-servers-section";
import { WhitelistedUsersSection } from "@/components/verification/whitelisted-users-section";
import { useFirstGuild } from "@/lib/use-first-guild";

type VerificationSettingsModalProps = {
  visible: boolean;
  onClose: () => void;
};

type Section = "general" | "high-risk" | "whitelist";

const SECTIONS: { id: Section; label: string }[] = [
  { id: "general", label: "General" },
  { id: "high-risk", label: "High Risk Servers" },
  { id: "whitelist", label: "Whitelisted Users" },
];

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
  const { guildId } = useFirstGuild();
  const [section, setSection] = useState<Section>("general");

  return (
    <FeatureConfigurationModal
      visible={visible}
      onClose={onClose}
      title="Verification Settings"
      description="Channels, roles, verification policy, high-risk servers, and whitelisted users."
      category="community"
      size="xl"
      footer={
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      }
    >
      <CNav variant="tabs" className="mb-4">
        {SECTIONS.map((item) => (
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
