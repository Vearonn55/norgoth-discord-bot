/**
 * Feed window card merge: always four cards, unconfigured stay visible.
 */
import { describe, expect, it } from "vitest";
import { feedNeedsSetup, formatFeedWindowToggleFeedback, mergeFeedWindowCards } from "@/lib/feed-windows";
import {
  DEFAULT_FEED_CONFIG,
  feedConfigPutPayload,
} from "@/stores/feed-channels-store";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";

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

  it("prefers confirmed config enabled over stale status", () => {
    const config = {
      ...DEFAULT_FEED_CONFIG,
      windows: {
        ...DEFAULT_FEED_CONFIG.windows,
        daily: {
          enabled: false,
          channel_id: "111",
          norgoth_managed: false,
        },
        weekly: {
          enabled: true,
          channel_id: "222",
          norgoth_managed: false,
        },
      },
    };
    const cards = mergeFeedWindowCards(config, [
      {
        key: "daily",
        configured: true,
        enabled: true,
        channel_id: "111",
        last_updated: null,
      },
      {
        key: "weekly",
        configured: true,
        enabled: true,
        channel_id: "222",
        last_updated: null,
      },
    ]);
    expect(cards.find((c) => c.key === "daily")?.enabled).toBe(false);
    expect(cards.find((c) => c.key === "weekly")?.enabled).toBe(true);
    expect(cards.find((c) => c.key === "monthly")?.enabled).toBe(false);
    expect(cards.find((c) => c.key === "all_time")?.enabled).toBe(false);
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

describe("feedConfigPutPayload", () => {
  it("omits the legacy minutes mirror so hour sliders do not 422", () => {
    const payload = feedConfigPutPayload({
      ...DEFAULT_FEED_CONFIG,
      daily_refresh_interval_hours: 6,
      refresh_interval_minutes: 360,
    });
    expect(payload.daily_refresh_interval_hours).toBe(6);
    expect("refresh_interval_minutes" in payload).toBe(false);
  });
});

describe("formatFeedWindowToggleFeedback", () => {
  it("uses localized period names for enable and disable", () => {
    expect(
      formatFeedWindowToggleFeedback(en.feedChannelsPage, "daily", true),
    ).toBe("Daily feed enabled.");
    expect(
      formatFeedWindowToggleFeedback(en.feedChannelsPage, "daily", false),
    ).toBe("Daily feed disabled.");
    expect(
      formatFeedWindowToggleFeedback(tr.feedChannelsPage, "weekly", true),
    ).toBe("Haftalık feed etkinleştirildi.");
    expect(
      formatFeedWindowToggleFeedback(tr.feedChannelsPage, "all_time", false),
    ).toBe("All-Time feed devre dışı bırakıldı.");
  });

  it("keeps a distinct generic window-updated message", () => {
    expect(en.feedChannelsPage.windowUpdatedSuccess).toBe(
      "Feed window updated.",
    );
    expect(tr.feedChannelsPage.windowUpdatedSuccess).toBe(
      "Feed penceresi güncellendi.",
    );
  });
});
