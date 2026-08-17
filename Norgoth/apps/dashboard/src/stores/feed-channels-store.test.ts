import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_FEED_CONFIG,
  type FeedConfig,
  type FeedStatus,
  useFeedChannelsStore,
} from "./feed-channels-store";

const GUILD = "111111111111111111";

function enabledWindow(channelId: string, enabled = true) {
  return {
    enabled,
    channel_id: channelId,
    norgoth_managed: false,
  };
}

function seedStore(config: FeedConfig, statusWindows: FeedStatus["windows"]) {
  useFeedChannelsStore.setState({
    config,
    status: {
      enabled: true,
      tracked_messages: 0,
      votes_total: 0,
      windows: statusWindows,
      warnings: [],
      top_message: null,
      last_refresh_at: {},
    },
    loading: false,
    busy: false,
    error: null,
    feedback: null,
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  useFeedChannelsStore.setState({
    config: null,
    status: null,
    loading: false,
    busy: false,
    error: null,
    feedback: null,
  });
});

describe("patchWindow", () => {
  it("persists false, reconciles stale status, and uses toggle feedback", async () => {
    const config: FeedConfig = {
      ...DEFAULT_FEED_CONFIG,
      enabled: true,
      windows: {
        ...DEFAULT_FEED_CONFIG.windows,
        daily: enabledWindow("1"),
        weekly: enabledWindow("2"),
      },
    };
    seedStore(config, [
      {
        key: "daily",
        configured: true,
        enabled: true,
        channel_id: "1",
        last_updated: null,
      },
      {
        key: "weekly",
        configured: true,
        enabled: true,
        channel_id: "2",
        last_updated: null,
      },
    ]);

    const nextConfig: FeedConfig = {
      ...config,
      windows: {
        ...config.windows,
        daily: enabledWindow("1", false),
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        expect(String(input)).toContain(`/windows/daily`);
        expect(init?.method).toBe("PATCH");
        expect(JSON.parse(String(init?.body))).toEqual({ enabled: false });
        return {
          ok: true,
          json: async () => ({ config: nextConfig }),
        };
      }),
    );

    const saved = await useFeedChannelsStore
      .getState()
      .patchWindow(GUILD, "daily", { enabled: false }, {
        successFeedback: "Daily feed disabled.",
      });

    const state = useFeedChannelsStore.getState();
    expect(saved?.windows.daily.enabled).toBe(false);
    expect(state.config?.windows.daily.enabled).toBe(false);
    expect(state.config?.windows.weekly.enabled).toBe(true);
    expect(state.status?.windows.find((w) => w.key === "daily")?.enabled).toBe(
      false,
    );
    expect(state.status?.windows.find((w) => w.key === "weekly")?.enabled).toBe(
      true,
    );
    expect(state.feedback).toBe("Daily feed disabled.");
    expect(state.feedback).not.toBe("Feed window updated.");
  });

  it("rolls back to the last confirmed state on failure", async () => {
    const config: FeedConfig = {
      ...DEFAULT_FEED_CONFIG,
      windows: {
        ...DEFAULT_FEED_CONFIG.windows,
        monthly: enabledWindow("3"),
      },
    };
    seedStore(config, [
      {
        key: "monthly",
        configured: true,
        enabled: true,
        channel_id: "3",
        last_updated: null,
      },
    ]);

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 403,
        json: async () => ({ detail: "Forbidden" }),
      })),
    );

    const saved = await useFeedChannelsStore
      .getState()
      .patchWindow(GUILD, "monthly", { enabled: false });

    const state = useFeedChannelsStore.getState();
    expect(saved).toBeNull();
    expect(state.config?.windows.monthly.enabled).toBe(true);
    expect(state.status?.windows[0]?.enabled).toBe(true);
    expect(state.error).toBe("Forbidden");
    expect(state.busy).toBe(false);
  });

  it("keeps the generic window-updated copy for channel edits", async () => {
    const config: FeedConfig = {
      ...DEFAULT_FEED_CONFIG,
      windows: {
        ...DEFAULT_FEED_CONFIG.windows,
        all_time: enabledWindow("4"),
      },
    };
    seedStore(config, []);
    const nextConfig: FeedConfig = {
      ...config,
      windows: {
        ...config.windows,
        all_time: enabledWindow("5"),
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ config: nextConfig }),
      })),
    );

    await useFeedChannelsStore.getState().patchWindow(
      GUILD,
      "all_time",
      { channel_id: "5", enabled: true },
      { successFeedback: "Feed window updated." },
    );
    expect(useFeedChannelsStore.getState().feedback).toBe(
      "Feed window updated.",
    );
  });
});
