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
  leaves: number;
  voice_uniques: number;
  has_data: boolean;
};

export type EngagementTotals = {
  messages: number;
  unique_authors: number;
  joins: number;
  leaves: number;
  voice_uniques: number;
  days_with_data: number;
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
 * Community KPIs derived from the same five daily primitives, using the exact
 * formulas defined in the plan:
 * - Engagement rate = unique_authors / member_count (needs member_count)
 * - Messages per active member = messages / unique_authors
 * - Net growth = joins − leaves
 */
export function computeCommunityKpis(
  totals: EngagementTotals,
  memberCountHint?: number | null
): {
  engagementRate: number | null;
  messagesPerActiveMember: number;
  netGrowth: number;
  activeMembers: number;
  voiceUniques: number;
} {
  const members = memberCountHint && memberCountHint > 0 ? memberCountHint : null;

  const engagementRate =
    members != null ? clampScore((totals.unique_authors / members) * 100) : null;

  const messagesPerActiveMember =
    totals.unique_authors > 0 ? totals.messages / totals.unique_authors : 0;

  return {
    engagementRate,
    messagesPerActiveMember,
    netGrowth: totals.joins - totals.leaves,
    activeMembers: totals.unique_authors,
    voiceUniques: totals.voice_uniques,
  };
}

export function percentDelta(current: number, previous: number): number | null {
  if (!Number.isFinite(current) || !Number.isFinite(previous)) return null;
  if (previous === 0) {
    return current === 0 ? 0 : null;
  }
  return ((current - previous) / previous) * 100;
}
