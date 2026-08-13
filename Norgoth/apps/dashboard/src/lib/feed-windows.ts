import type { FeedConfig, FeedWindowKey } from "@/stores/feed-channels-store";
import { FEED_WINDOW_LABELS } from "@/stores/feed-channels-store";

export type FeedWindowCard = {
  key: FeedWindowKey;
  label: string;
  configured: boolean;
  enabled: boolean;
  channel_id: string | null;
  last_updated: string | null;
  cadence_label?: string | null;
  next_refresh_at?: string | null;
  remaining_seconds?: number | null;
};

const WINDOW_ORDER: FeedWindowKey[] = [
  "daily",
  "weekly",
  "monthly",
  "all_time",
];

const DEFAULT_CADENCE: Record<FeedWindowKey, string> = {
  daily: "Every 1 hour",
  weekly: "Every week from configuration anchor",
  monthly: "Every calendar month from configuration anchor",
  all_time: "Every 24 hours from configuration anchor",
};

/** Always return four cards so unconfigured windows stay visible (grey). */
export function mergeFeedWindowCards(
  config: FeedConfig | null,
  statusWindows?: Array<{
    key: FeedWindowKey;
    configured: boolean;
    enabled: boolean;
    channel_id: string | null;
    last_updated: string | null;
    cadence_label?: string | null;
    next_refresh_at?: string | null;
    remaining_seconds?: number | null;
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
    const dailyHours =
      window?.refresh_interval_hours ??
      config?.daily_refresh_interval_hours ??
      1;
    return {
      key,
      label: FEED_WINDOW_LABELS[key],
      configured,
      enabled: status?.enabled ?? Boolean(window?.enabled && configured),
      channel_id: channelId,
      last_updated: status?.last_updated ?? null,
      cadence_label:
        status?.cadence_label ??
        (key === "daily"
          ? `Every ${dailyHours} hour${dailyHours === 1 ? "" : "s"}`
          : DEFAULT_CADENCE[key]),
      next_refresh_at:
        status?.next_refresh_at ?? window?.next_refresh_at ?? null,
      remaining_seconds: status?.remaining_seconds ?? null,
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
