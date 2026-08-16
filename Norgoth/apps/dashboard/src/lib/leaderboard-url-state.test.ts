import { describe, expect, it } from "vitest";
import {
  isLeaderboardMetric,
  parseLeaderboardMetric,
} from "@/lib/leaderboard-url-state";

describe("leaderboard URL metric", () => {
  it("accepts the three real tab identifiers", () => {
    expect(isLeaderboardMetric("text")).toBe(true);
    expect(isLeaderboardMetric("voice")).toBe(true);
    expect(isLeaderboardMetric("net_upvotes")).toBe(true);
  });

  it("falls back to text for missing or invalid values", () => {
    expect(parseLeaderboardMetric(null)).toBe("text");
    expect(parseLeaderboardMetric("overall")).toBe("text");
    expect(parseLeaderboardMetric("")).toBe("text");
  });
});
