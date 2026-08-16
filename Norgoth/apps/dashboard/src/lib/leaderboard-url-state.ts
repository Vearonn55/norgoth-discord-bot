import type { LeaderboardMetric } from "@/stores/leveling-store";

export const LEADERBOARD_METRICS: readonly LeaderboardMetric[] = [
  "text",
  "voice",
  "net_upvotes",
];

export function isLeaderboardMetric(
  value: string | null | undefined,
): value is LeaderboardMetric {
  return (
    value === "text" || value === "voice" || value === "net_upvotes"
  );
}

export function parseLeaderboardMetric(
  value: string | null | undefined,
): LeaderboardMetric {
  return isLeaderboardMetric(value) ? value : "text";
}
