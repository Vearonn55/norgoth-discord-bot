import { afterEach, describe, expect, it, vi } from "vitest";
import { useGuildStore, type GuildResources } from "./guild-store";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const guildA: GuildResources = {
  guild_id: "guild-a",
  guild_name: "Alpha",
  channels: [{ id: "10", name: "general" }],
  roles: [],
};

function stubWindow() {
  vi.stubGlobal("window", {
    setTimeout,
    clearTimeout,
    localStorage: {
      getItem: () => null,
      setItem: () => undefined,
      removeItem: () => undefined,
    },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  useGuildStore.setState({
    guildId: null,
    selectedGuild: null,
    resources: null,
    loading: false,
    error: null,
    refreshingChannels: false,
    refreshingKind: null,
    channelRefreshNotice: null,
  });
});

describe("refreshChannels", () => {
  it("keeps the previous snapshot until the fresh list arrives", async () => {
    stubWindow();
    let resolveFetch: ((value: Response) => void) | undefined;
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    useGuildStore.setState({
      guildId: "guild-a",
      resources: guildA,
      loading: false,
      refreshingChannels: false,
      channelRefreshNotice: null,
    });

    const pending = useGuildStore.getState().refreshChannels();
    expect(useGuildStore.getState().resources).toEqual(guildA);
    expect(useGuildStore.getState().refreshingChannels).toBe(true);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      "/guilds/guild-a/discord-resources?refresh=1",
    );

    const next: GuildResources = {
      ...guildA,
      channels: [
        { id: "10", name: "general" },
        { id: "11", name: "news" },
      ],
    };
    resolveFetch?.(jsonResponse(next));
    await pending;

    expect(useGuildStore.getState().resources?.channels.map((c) => c.id)).toEqual(
      ["10", "11"],
    );
    expect(useGuildStore.getState().channelRefreshNotice).toEqual({
      type: "success",
      kind: "channels",
    });
  });

  it("ignores a stale refresh after the selected guild changes", async () => {
    stubWindow();
    let resolveFetch: ((value: Response) => void) | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            resolveFetch = resolve;
          }),
      ),
    );
    useGuildStore.setState({
      guildId: "guild-a",
      resources: guildA,
      loading: false,
      refreshingChannels: false,
      channelRefreshNotice: null,
    });

    const pending = useGuildStore.getState().refreshChannels();
    useGuildStore.getState().clearGuild();
    resolveFetch?.(
      jsonResponse({
        ...guildA,
        channels: [{ id: "99", name: "stale" }],
      }),
    );
    await pending;

    expect(useGuildStore.getState().guildId).toBeNull();
    expect(useGuildStore.getState().resources).toBeNull();
  });

  it("warns when Discord returns the cached snapshot", async () => {
    stubWindow();
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...guildA,
            source: "cache",
            refreshed: false,
          }),
        ),
      ),
    );
    useGuildStore.setState({
      guildId: "guild-a",
      resources: guildA,
      loading: false,
      refreshingChannels: false,
      channelRefreshNotice: null,
    });

    await useGuildStore.getState().refreshChannels();

    expect(useGuildStore.getState().channelRefreshNotice).toEqual({
      type: "warning",
      kind: "channels",
    });
  });

  it("scopes success notices to the requested kind", async () => {
    stubWindow();
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...guildA,
            source: "fresh",
            refreshed: true,
          }),
        ),
      ),
    );
    useGuildStore.setState({
      guildId: "guild-a",
      resources: guildA,
      loading: false,
      refreshingChannels: false,
      channelRefreshNotice: { type: "success", kind: "channels" },
    });

    await useGuildStore.getState().refreshRoles();

    expect(useGuildStore.getState().channelRefreshNotice).toEqual({
      type: "success",
      kind: "roles",
    });
  });
});
