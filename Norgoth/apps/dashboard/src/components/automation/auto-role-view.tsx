"use client";

import { cilUserFollow } from "@coreui/icons";
import { CAlert } from "@coreui/react";
import { PageHeader } from "@/components/layout/page-header";
import { ManagingGuildLabel } from "@/components/layout/managing-guild-label";
import { AutomationSettingsPanel } from "@/components/automation/automation-settings-panel";
import { Icon } from "@/components/ui/icon";
import { MutedSection } from "@/components/ui/feature-muting";
import { useFeatureInfo } from "@/lib/feature-info";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useAutomationStore } from "@/stores/automation-store";
import { useLocaleDict } from "@/lib/locale-dict";

export function AutoRoleView() {
  const info = useFeatureInfo("autoRole");
  const dict = useLocaleDict();
  const d = dict.welcomeAutoRolePage;
  const { guildId } = useFirstGuild();
  const config = useAutomationStore((s) => s.config);
  const loading = useAutomationStore((s) => s.loading);
  const saving = useAutomationStore((s) => s.saving);
  const error = useAutomationStore((s) => s.error);
  const setAutoRoleEnabled = useAutomationStore((s) => s.setAutoRoleEnabled);

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={info?.title ?? "Auto Role"}
        icon={<Icon icon={cilUserFollow} size="xl" />}
        category="roles"
        description={<ManagingGuildLabel />}
        infoKey="autoRole"
        masterToggle={{
          enabled: config.auto_role_enabled,
          loading: loading || saving || !guildId,
          label: d.autoRoleAria,
          showLabel: false,
          onChange: (checked) => {
            if (!guildId) return;
            void setAutoRoleEnabled(guildId, checked);
          },
        }}
      />

      {error ? (
        <CAlert color="danger" className="mb-0">
          {error}
        </CAlert>
      ) : null}

      <MutedSection enabled={config.auto_role_enabled}>
        <AutomationSettingsPanel section="autorole" />
      </MutedSection>
    </div>
  );
}
