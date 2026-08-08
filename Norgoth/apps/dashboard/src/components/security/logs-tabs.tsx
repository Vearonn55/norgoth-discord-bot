"use client";

import { useState } from "react";
import {
  SegmentedControl,
  SegmentedPanel,
} from "@/components/ui/segmented-control";
import { AuditLogsPanel } from "@/components/security/audit-logs-panel";
import { LoggingConfigurationsPanel } from "@/components/security/logging-configurations-panel";

const TABS = [
  { id: "audit", label: "Audit Logs" },
  { id: "config", label: "Logging Configurations" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function LogsTabs() {
  const [activeTab, setActiveTab] = useState<TabId>("audit");

  return (
    <div className="d-flex flex-column gap-4">
      <SegmentedControl
        options={[...TABS]}
        value={activeTab}
        onChange={setActiveTab}
        ariaLabel="Logging sections"
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
