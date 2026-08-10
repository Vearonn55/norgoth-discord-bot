import type { FeedConfig, FeedWindowKey } from "@/stores/feed-channels-store";
import { FEED_WINDOW_LABELS } from "@/stores/feed-channels-store";

export type FeedWindowCard = {
  key: FeedWindowKey;
  label: string;
  configured: boolean;
  enabled: boolean;
  channel_id: string | null;
  last_updated: string | null;
};

const WINDOW_ORDER: FeedWindowKey[] = [
  "daily",
  "weekly",
  "monthly",
  "all_time",
];

/** Always return four cards so unconfigured windows stay visible (grey). */
export function mergeFeedWindowCards(
  config: FeedConfig | null,
  statusWindows?: Array<{
    key: FeedWindowKey;
    configured: boolean;
    enabled: boolean;
    channel_id: string | null;
    last_updated: string | null;
  }> | null
): FeedWindowCard[] {
  const byKey = new Map(
    (statusWindows ?? []).map((row) => [row.key, row] as const)
  );

  return WINDOW_ORDER.map((key) => {
    const window = config?.windows?.[key];
    const status = byKey.get(key);
    const channelId = status?.channel_id ?? window?.channel_id ?? null;
    const configured =
      status?.configured ?? Boolean(channelId && String(channelId).length > 0);
    return {
      key,
      label: FEED_WINDOW_LABELS[key],
      configured,
      enabled: Boolean(status?.enabled ?? window?.enabled),
      channel_id: channelId,
      last_updated:
        status?.last_updated ??
        config?.last_refresh_at?.[key] ??
        null,
    };
  });
}

export function feedNeedsSetup(config: FeedConfig | null): boolean {
  if (!config) return true;
  const hasSources = (config.source_channel_ids ?? []).length > 0;
  const hasWindow = Object.values(config.windows ?? {}).some(
    (window) => Boolean(window?.channel_id)
  );
  return !hasSources && !hasWindow;
}
