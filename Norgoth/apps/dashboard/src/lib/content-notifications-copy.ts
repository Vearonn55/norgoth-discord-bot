"use client";

import { useParams } from "next/navigation";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";

export type ContentNotificationsCopy = typeof en.contentNotifications;

/** Locale-aware Content Notifications UI strings. */
export function useContentNotificationsCopy(): ContentNotificationsCopy {
  const params = useParams();
  const lang = String(params?.lang || "en");
  return (lang === "tr" ? tr : en).contentNotifications;
}

export function localizeSubscriptionStatus(
  status: string,
  copy: ContentNotificationsCopy,
): string {
  const map: Record<string, string> = {
    waiting_first_event: copy.statusWaitingFirstEvent,
    subscription_healthy: copy.statusSubscriptionHealthy,
    upstream_subscribe_failed: copy.statusUpstreamSubscribeFailed,
    paused: copy.statusPaused,
    blocked: copy.statusBlocked,
    discord_permission_missing: copy.statusDiscordPermissionMissing,
    webhook_missing: copy.statusWebhookMissing,
  };
  return map[status] ?? status.replaceAll("_", " ");
}
