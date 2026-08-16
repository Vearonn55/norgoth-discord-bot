"use client";

import { useRef, useState } from "react";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { Button } from "@/components/ui/button";
import { TemplatesPanel, type TemplatesPanelHandle } from "@/components/content-notifications/templates-panel";
import { SenderStylesPanel, type SenderStylesPanelHandle } from "@/components/content-notifications/sender-styles-panel";
import { DeliveryHistoryPanel } from "@/components/content-notifications/delivery-history-panel";
import { AnalyticsPanel } from "@/components/content-notifications/analytics-panel";
import { useContentNotificationsCopy } from "@/lib/content-notifications-copy";
import { confirmDirtyClose } from "@/lib/cn-url-state";
import { useCnUrlState } from "@/lib/use-cn-url-state";

export function ContentNotificationsModals() {
  const copy = useContentNotificationsCopy();
  const { state, patchState } = useCnUrlState();
  const templatesRef = useRef<TemplatesPanelHandle>(null);
  const stylesRef = useRef<SenderStylesPanelHandle>(null);
  const [templatesDirty, setTemplatesDirty] = useState(false);
  const [stylesDirty, setStylesDirty] = useState(false);

  const closeInventory = () => patchState({ panel: null, account: null });

  return (
    <>
      <FeatureConfigurationModal
        visible={state.panel === "templates"}
        title={copy.templatesPageTitle}
        description={copy.templatesPageDescription}
        category="messages"
        size="xl"
        onClose={() => {
          if (!confirmDirtyClose(templatesDirty, copy.unsavedConfirm)) return;
          closeInventory();
        }}
        onSave={async () => {
          const ok = await templatesRef.current?.save();
          if (ok) closeInventory();
        }}
      >
        <TemplatesPanel
          ref={templatesRef}
          onDirtyChange={setTemplatesDirty}
        />
      </FeatureConfigurationModal>

      <FeatureConfigurationModal
        visible={state.panel === "sender-styles"}
        title={copy.stylesPageTitle}
        description={copy.stylesPageDescription}
        category="messages"
        size="lg"
        onClose={() => {
          if (!confirmDirtyClose(stylesDirty, copy.unsavedConfirm)) return;
          closeInventory();
        }}
        onSave={async () => {
          const ok = await stylesRef.current?.save();
          if (ok) closeInventory();
        }}
      >
        <SenderStylesPanel ref={stylesRef} onDirtyChange={setStylesDirty} />
      </FeatureConfigurationModal>

      <FeatureConfigurationModal
        visible={state.panel === "history"}
        title={copy.historyModalTitle}
        description={copy.historyPageDescription}
        category="messages"
        size="xl"
        onClose={closeInventory}
        footer={
          <Button type="button" variant="secondary" onClick={closeInventory}>
            {copy.close}
          </Button>
        }
      >
        <DeliveryHistoryPanel />
      </FeatureConfigurationModal>

      <FeatureConfigurationModal
        visible={state.panel === "analytics"}
        title={copy.analyticsPageTitle}
        description={copy.analyticsPageDescription}
        category="messages"
        size="xl"
        onClose={closeInventory}
        footer={
          <Button type="button" variant="secondary" onClick={closeInventory}>
            {copy.close}
          </Button>
        }
      >
        <AnalyticsPanel />
      </FeatureConfigurationModal>
    </>
  );
}
