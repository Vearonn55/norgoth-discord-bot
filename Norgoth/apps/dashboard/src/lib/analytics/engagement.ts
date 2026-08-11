/**
 * Engagement score weights and derived rates from daily analytics buckets.
 * Real data only — callers must handle insufficient history.
 */

export const ENGAGEMENT_WEIGHTS = {
  activeMemberRate: 0.35,
  messageParticipation: 0.3,
  voiceParticipation: 0.2,
  newMemberActivation: 0.15,
} as const;

export type EngagementDayPoint = {
  date: string;
  messages: number;
  unique_authors: number;
  joins: number;
  rejoins: number;
  leaves: number;
  voice_uniques: number;
  /** Total member population recorded that day; null when no snapshot. */
  member_count: number | null;
  has_data: boolean;
};

export type EngagementTotals = {
  messages: number;
  unique_authors: number;
  joins: number;
  rejoins: number;
  leaves: number;
  voice_uniques: number;
  days_with_data: number;
  /**
   * Snapshot-derived population KPIs. All null when the window has no
   * member_count snapshots (bot was offline / feature just enabled).
   */
  start_members: number | null;
  end_members: number | null;
  net_member_change: number | null;
  net_growth_rate: number | null;
  churn_rate: number | null;
  retention_rate: number | null;
  /** First-time joins only (rejoins excluded). */
  new_members: number;
};

export type EngagementResponse = {
  guild_id: string;
  range: number;
  series: EngagementDayPoint[];
  totals: EngagementTotals;
  previous_totals: EngagementTotals;
  insufficient_history: boolean;
};

export type EngagementRange = 7 | 30 | 90;

/** Clamp 0–100. */
function clampScore(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(100, n));
}

/**
 * Heuristic rates when we lack member_count:
 * - Active Member Rate: unique authors / max(unique authors, joins*3, 1) scaled
 * - Message participation: messages per unique author (cap)
 * - Voice: voice_uniques vs unique_authors
 * - New member activation: min(unique_authors, joins) / max(joins, 1)
 */
export function computeEngagementMetrics(
  totals: EngagementTotals,
  memberCountHint?: number | null
): {
  activeMemberRate: number;
  messageParticipation: number;
  voiceParticipation: number;
  newMemberActivation: number;
  score: number;
} {
  const members = Math.max(memberCountHint ?? 0, totals.unique_authors, 1);

  const activeMemberRate = clampScore(
    (totals.unique_authors / members) * 100
  );

  const msgsPerAuthor =
    totals.unique_authors > 0
      ? totals.messages / totals.unique_authors
      : 0;
  // ~10 msgs/author over the window → 100
  const messageParticipation = clampScore((msgsPerAuthor / 10) * 100);

  const voiceParticipation = clampScore(
    totals.unique_authors > 0
      ? (totals.voice_uniques / totals.unique_authors) * 100
      : 0
  );

  const newMemberActivation = clampScore(
    totals.joins > 0
      ? (Math.min(totals.unique_authors, totals.joins) / totals.joins) * 100
      : totals.unique_authors > 0
        ? 50
        : 0
  );

  const score = clampScore(
    activeMemberRate * ENGAGEMENT_WEIGHTS.activeMemberRate +
      messageParticipation * ENGAGEMENT_WEIGHTS.messageParticipation +
      voiceParticipation * ENGAGEMENT_WEIGHTS.voiceParticipation +
      newMemberActivation * ENGAGEMENT_WEIGHTS.newMemberActivation
  );

  return {
    activeMemberRate,
    messageParticipation,
    voiceParticipation,
    newMemberActivation,
    score,
  };
}

/**
 * Community KPIs derived from the daily primitives:
 * - Engagement rate = unique_authors / member_count (needs member_count)
 * - Messages per active member = messages / unique_authors
 * - Net growth: prefer the snapshot-derived population delta (end − start of
 *   window), which reflects reality even when events were missed. Falls back to
 *   first-time joins − leaves when no snapshots exist. Rejoins are always
 *   excluded from "new members" and surfaced separately.
 * - Churn / retention: normalized against the starting population when
 *   snapshots exist, otherwise null (unknown).
 */
export function computeCommunityKpis(
  totals: EngagementTotals,
  memberCountHint?: number | null
): {
  engagementRate: number | null;
  messagesPerActiveMember: number;
  netGrowth: number;
  netGrowthRate: number | null;
  churnRate: number | null;
  retentionRate: number | null;
  newMembers: number;
  rejoins: number;
  activeMembers: number;
  voiceUniques: number;
  memberCount: number | null;
} {
  // Denominator preference: explicit hint → end-of-window snapshot → unknown.
  const members =
    memberCountHint && memberCountHint > 0
      ? memberCountHint
      : totals.end_members && totals.end_members > 0
        ? totals.end_members
        : null;

  const engagementRate =
    members != null ? clampScore((totals.unique_authors / members) * 100) : null;

  const messagesPerActiveMember =
    totals.unique_authors > 0 ? totals.messages / totals.unique_authors : 0;

  // Prefer the true population delta from snapshots; fall back to joins−leaves.
  const netGrowth =
    totals.net_member_change != null
      ? totals.net_member_change
      : totals.joins - totals.leaves;

  return {
    engagementRate,
    messagesPerActiveMember,
    netGrowth,
    netGrowthRate: totals.net_growth_rate,
    churnRate: totals.churn_rate,
    retentionRate: totals.retention_rate,
    newMembers: totals.new_members ?? totals.joins,
    rejoins: totals.rejoins,
    activeMembers: totals.unique_authors,
    voiceUniques: totals.voice_uniques,
    memberCount: members,
  };
}

export function percentDelta(current: number, previous: number): number | null {
  if (!Number.isFinite(current) || !Number.isFinite(previous)) return null;
  if (previous === 0) {
    return current === 0 ? 0 : null;
  }
  return ((current - previous) / previous) * 100;
}
