import { describe, expect, it } from "vitest";
import {
  computeCommunityKpis,
  type EngagementTotals,
} from "@/lib/analytics/engagement";

function makeTotals(overrides: Partial<EngagementTotals> = {}): EngagementTotals {
  return {
    messages: 1200,
    unique_authors: 80,
    joins: 25,
    rejoins: 6,
    leaves: 10,
    voice_uniques: 18,
    days_with_data: 7,
    start_members: null,
    end_members: null,
    net_member_change: null,
    net_growth_rate: null,
    churn_rate: null,
    retention_rate: null,
    new_members: 25,
    ...overrides,
  };
}

const totals = makeTotals();

describe("computeCommunityKpis", () => {
  it("derives engagement rate as unique_authors / member_count", () => {
    const kpis = computeCommunityKpis(totals, 400);
    // 80 / 400 = 20%
    expect(kpis.engagementRate).toBe(20);
  });

  it("falls back to end-of-window snapshot for the member denominator", () => {
    const kpis = computeCommunityKpis(
      makeTotals({ end_members: 400 }),
      null
    );
    expect(kpis.engagementRate).toBe(20);
    expect(kpis.memberCount).toBe(400);
  });

  it("returns null engagement rate when member count is unknown", () => {
    expect(computeCommunityKpis(totals, null).engagementRate).toBeNull();
    expect(computeCommunityKpis(totals, 0).engagementRate).toBeNull();
  });

  it("derives messages per active member as messages / unique_authors", () => {
    const kpis = computeCommunityKpis(totals, 400);
    // 1200 / 80 = 15
    expect(kpis.messagesPerActiveMember).toBe(15);
  });

  it("guards divide-by-zero when there are no active authors", () => {
    const empty = makeTotals({
      messages: 0,
      unique_authors: 0,
      joins: 0,
      rejoins: 0,
      leaves: 0,
      voice_uniques: 0,
      days_with_data: 0,
      new_members: 0,
    });
    expect(computeCommunityKpis(empty, 100).messagesPerActiveMember).toBe(0);
  });

  it("falls back to joins - leaves for net growth when no snapshots (excludes rejoins)", () => {
    // 25 joins - 10 leaves = 15; the 6 rejoins must NOT affect net growth.
    expect(computeCommunityKpis(totals, 400).netGrowth).toBe(15);
    expect(
      computeCommunityKpis(makeTotals({ rejoins: 100 }), 400).netGrowth
    ).toBe(15);
    expect(
      computeCommunityKpis(makeTotals({ joins: 5, leaves: 12 }), 400).netGrowth
    ).toBe(-7);
  });

  it("prefers the snapshot-derived population delta for net growth", () => {
    const kpis = computeCommunityKpis(
      makeTotals({
        start_members: 400,
        end_members: 430,
        net_member_change: 30,
        net_growth_rate: 0.075,
      }),
      400
    );
    // Uses the population delta (30), not joins - leaves (15).
    expect(kpis.netGrowth).toBe(30);
    expect(kpis.netGrowthRate).toBeCloseTo(0.075);
  });

  it("passes through churn and retention when provided", () => {
    const kpis = computeCommunityKpis(
      makeTotals({ churn_rate: 0.025, retention_rate: 0.975 }),
      400
    );
    expect(kpis.churnRate).toBeCloseTo(0.025);
    expect(kpis.retentionRate).toBeCloseTo(0.975);
  });

  it("passes through rejoins, active members and voice uniques", () => {
    const kpis = computeCommunityKpis(totals, 400);
    expect(kpis.rejoins).toBe(6);
    expect(kpis.activeMembers).toBe(80);
    expect(kpis.voiceUniques).toBe(18);
  });
});
