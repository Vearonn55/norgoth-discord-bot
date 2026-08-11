import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useEmbedMessagesStore } from "@/stores/embed-messages-store";

type FetchArgs = { url: string; method: string; body: unknown };

function mockFetch(status = 200, payload: unknown = {}) {
  const calls: FetchArgs[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({
      url: String(input),
      method: init?.method ?? "GET",
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    } as Response;
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

const draft = {
  id: "m-1",
  guild_id: "g-1",
  name: "Draft",
  description: "",
  content: "hi",
  embed_json: null,
  version: 1,
  has_published: false,
  deployment_count: 0,
  synced_count: 0,
  current_count: 0,
  needs_resync: false,
  sync_status: "draft_only",
  created_by: null,
  created_at: null,
  updated_at: null,
  deliveries: [],
};

beforeEach(() => {
  useEmbedMessagesStore.setState({ messages: [], loading: false, error: null });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("embed messages store (content-only drafts)", () => {
  it("create() sends a content-only body with no publish targets", async () => {
    const calls = mockFetch(200, draft);
    await useEmbedMessagesStore.getState().create("g-1", {
      name: "Draft",
      description: "",
      content: "hi",
      embed_json: null,
    });

    expect(calls).toHaveLength(1);
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/guilds/g-1/embed-messages");
    expect(calls[0].body).not.toHaveProperty("target_channel_ids");
    expect(calls[0].body).toMatchObject({ name: "Draft", content: "hi" });
  });

  it("deploy() posts the chosen channel to /send", async () => {
    const calls = mockFetch(200, { ...draft, deployment_count: 1 });
    useEmbedMessagesStore.setState({ messages: [draft as never] });
    await useEmbedMessagesStore.getState().deploy("g-1", "m-1", "chan-1");

    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/guilds/g-1/embed-messages/m-1/send");
    expect(calls[0].body).toEqual({ channel_id: "chan-1" });
  });

  it("resync() hits the deployment-driven /resync route", async () => {
    const calls = mockFetch(200, draft);
    await useEmbedMessagesStore.getState().resync("g-1", "m-1");

    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/guilds/g-1/embed-messages/m-1/resync");
  });

  it("remove() forwards the force flag for the dependency guard", async () => {
    const calls = mockFetch(200, { ok: true });
    await useEmbedMessagesStore
      .getState()
      .remove("g-1", "m-1", { force: true });

    expect(calls[0].method).toBe("DELETE");
    expect(calls[0].body).toEqual({
      delete_discord_messages: false,
      force: true,
    });
  });

  it("remove() surfaces the 409 dependency error and keeps the draft", async () => {
    mockFetch(409, { detail: { message: "in use" } });
    useEmbedMessagesStore.setState({ messages: [draft as never] });
    const ok = await useEmbedMessagesStore.getState().remove("g-1", "m-1");

    expect(ok).toBe(false);
    expect(useEmbedMessagesStore.getState().messages).toHaveLength(1);
    expect(useEmbedMessagesStore.getState().error).toBeTruthy();
  });
});
