/**
 * Feed window card merge: always four cards, unconfigured stay visible.
 */
import { describe, expect, it } from "vitest";
import { feedNeedsSetup, mergeFeedWindowCards } from "@/lib/feed-windows";
import { DEFAULT_FEED_CONFIG } from "@/stores/feed-channels-store";

describe("mergeFeedWindowCards", () => {
  it("returns four cards for empty config", () => {
    const cards = mergeFeedWindowCards(null);
    expect(cards).toHaveLength(4);
    expect(cards.every((c) => !c.configured)).toBe(true);
    expect(cards.map((c) => c.key)).toEqual([
      "daily",
      "weekly",
      "monthly",
      "all_time",
    ]);
  });

  it("marks configured windows from channel_id", () => {
    const config = {
      ...DEFAULT_FEED_CONFIG,
      windows: {
        ...DEFAULT_FEED_CONFIG.windows,
        daily: {
          enabled: true,
          channel_id: "111",
          norgoth_managed: false,
        },
      },
    };
    const cards = mergeFeedWindowCards(config);
    const daily = cards.find((c) => c.key === "daily");
    expect(daily?.configured).toBe(true);
    expect(daily?.enabled).toBe(true);
    expect(cards.filter((c) => !c.configured)).toHaveLength(3);
  });
});

describe("feedNeedsSetup", () => {
  it("is true when no sources and no windows", () => {
    expect(feedNeedsSetup(DEFAULT_FEED_CONFIG)).toBe(true);
  });

  it("is false when a window has a channel", () => {
    expect(
      feedNeedsSetup({
        ...DEFAULT_FEED_CONFIG,
        windows: {
          ...DEFAULT_FEED_CONFIG.windows,
          weekly: {
            enabled: true,
            channel_id: "222",
            norgoth_managed: false,
          },
        },
      })
    ).toBe(false);
  });
});
