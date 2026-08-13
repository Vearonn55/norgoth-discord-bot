"use client";

import { useMemo, useState } from "react";
import {
  SegmentedControl,
  SegmentedPanel,
} from "@/components/ui/segmented-control";
import { AuditLogsPanel } from "@/components/security/audit-logs-panel";
import { LoggingConfigurationsPanel } from "@/components/security/logging-configurations-panel";
import { useLocaleDict } from "@/lib/locale-dict";

type TabId = "audit" | "config";

export function LogsTabs() {
  const dict = useLocaleDict();
  const d = dict.discordLogsPage;
  const [activeTab, setActiveTab] = useState<TabId>("audit");

  const tabs = useMemo(
    () =>
      [
        { id: "audit" as const, label: d.tabAudit },
        { id: "config" as const, label: d.tabConfig },
      ] as const,
    [d.tabAudit, d.tabConfig],
  );

  return (
    <div className="d-flex flex-column gap-4">
      <SegmentedControl
        options={[...tabs]}
        value={activeTab}
        onChange={setActiveTab}
        ariaLabel={d.tabsAria}
      />

      <SegmentedPanel>
        {activeTab === "audit" ? (
          <AuditLogsPanel />
        ) : (
          <LoggingConfigurationsPanel />
        )}
      </SegmentedPanel>
    </div>
  );
}
