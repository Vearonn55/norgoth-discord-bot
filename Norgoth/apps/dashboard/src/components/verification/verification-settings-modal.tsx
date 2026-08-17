"use client";

import { useMemo, useState } from "react";
import { CNav, CNavItem, CNavLink } from "@coreui/react";
import { useParams } from "next/navigation";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { VerificationSettingsForm } from "@/components/verification/verification-settings-form";
import { HighRiskServersSection } from "@/components/verification/high-risk-servers-section";
import { WhitelistedUsersSection } from "@/components/verification/whitelisted-users-section";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useLocaleDict } from "@/lib/locale-dict";
import { useVerificationStore } from "@/stores/verification-store";

type VerificationSettingsModalProps = {
  visible: boolean;
  onClose: () => void;
};

type Section = "general" | "high-risk" | "whitelist";

/**
 * Verification Settings popout. Save persists configuration, then closes.
 * Discord panel publish runs afterward and does not keep the popup open.
 */
export function VerificationSettingsModal({
  visible,
  onClose,
}: VerificationSettingsModalProps) {
  const dict = useLocaleDict();
  const params = useParams();
  const lang = String(params?.lang || "en");
  const d = dict.verificationPage;
  const { guildId } = useFirstGuild();
  const [section, setSection] = useState<Section>("general");
  const saving = useVerificationStore((s) => s.saving);
  const publishing = useVerificationStore((s) => s.publishing);
  const error = useVerificationStore((s) => s.error);
  const setError = useVerificationStore((s) => s.setError);
  const save = useVerificationStore((s) => s.save);
  const publishPanel = useVerificationStore((s) => s.publishPanel);
  const loadConfig = useVerificationStore((s) => s.loadConfig);

  const sections = useMemo(
    () =>
      [
        { id: "general" as const, label: d.tabGeneral },
        { id: "high-risk" as const, label: d.tabHighRisk },
        { id: "whitelist" as const, label: d.tabWhitelist },
      ] satisfies { id: Section; label: string }[],
    [d.tabGeneral, d.tabHighRisk, d.tabWhitelist],
  );

  const busy = saving || publishing;

  return (
    <FeatureConfigurationModal
      visible={visible}
      onClose={() => {
        if (busy) return;
        setError(null);
        onClose();
      }}
      title={d.settingsModalTitle}
      description={d.settingsModalDesc}
      category="community"
      size="xl"
      cancelLabel={d.close}
      saveLabel={d.saveSettings}
      saving={busy}
      error={section === "general" ? error : null}
      onSave={
        section === "general"
          ? async () => {
              if (!guildId || busy) return;
              const result = await save(guildId);
              if (!result.ok) return;
              onClose();
              void publishPanel(guildId, lang).finally(() => {
                void loadConfig(guildId);
              });
            }
          : undefined
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
