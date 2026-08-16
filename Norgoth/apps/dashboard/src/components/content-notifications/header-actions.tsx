"use client";

import { Button } from "@/components/ui/button";
import { useContentNotificationsCopy } from "@/lib/content-notifications-copy";
import { useCnUrlState } from "@/lib/use-cn-url-state";

export function ContentNotificationsHeaderActions() {
  const copy = useContentNotificationsCopy();
  const { patchState } = useCnUrlState();

  return (
    <div className="d-flex gap-2 flex-wrap">
      <Button
        type="button"
        size="sm"
        variant="secondary"
        onClick={() => patchState({ panel: "templates", account: null })}
      >
        {copy.navTemplates}
      </Button>
      <Button
        type="button"
        size="sm"
        variant="secondary"
        onClick={() => patchState({ panel: "sender-styles", account: null })}
      >
        {copy.navSenderStyles}
      </Button>
      <Button
        type="button"
        size="sm"
        variant="secondary"
        onClick={() => patchState({ panel: "history", account: null })}
      >
        {copy.navHistory}
      </Button>
      <Button
        type="button"
        size="sm"
        variant="secondary"
        onClick={() => patchState({ panel: "analytics", account: null })}
      >
        {copy.navAnalytics}
      </Button>
    </div>
  );
}
