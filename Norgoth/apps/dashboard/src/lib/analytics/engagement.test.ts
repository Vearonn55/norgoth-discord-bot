import { describe, expect, it } from "vitest";
import {
  computeCommunityKpis,
  type EngagementTotals,
} from "@/lib/analytics/engagement";

const totals: EngagementTotals = {
  messages: 1200,
  unique_authors: 80,
  joins: 25,
  leaves: 10,
  voice_uniques: 18,
  days_with_data: 7,
};

describe("computeCommunityKpis", () => {
  it("derives engagement rate as unique_authors / member_count", () => {
    const kpis = computeCommunityKpis(totals, 400);
    // 80 / 400 = 20%
    expect(kpis.engagementRate).toBe(20);
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
    const empty: EngagementTotals = {
      messages: 0,
      unique_authors: 0,
      joins: 0,
      leaves: 0,
      voice_uniques: 0,
      days_with_data: 0,
    };
    expect(computeCommunityKpis(empty, 100).messagesPerActiveMember).toBe(0);
  });

  it("derives net growth as joins - leaves (can be negative)", () => {
    expect(computeCommunityKpis(totals, 400).netGrowth).toBe(15);
    expect(
      computeCommunityKpis({ ...totals, joins: 5, leaves: 12 }, 400).netGrowth
    ).toBe(-7);
  });

  it("passes through active members and voice uniques", () => {
    const kpis = computeCommunityKpis(totals, 400);
    expect(kpis.activeMembers).toBe(80);
    expect(kpis.voiceUniques).toBe(18);
  });
});
