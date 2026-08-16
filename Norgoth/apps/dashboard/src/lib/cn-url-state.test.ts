import { describe, expect, it } from "vitest";
import {
  accountsListQuery,
  clampPage,
  parseCnUrlState,
  serializeCnUrlState,
  shouldCloseDirtyModal,
  withCnPlatform,
} from "@/lib/cn-url-state";

describe("cn url state", () => {
  it("parses platform, page, panel, and account", () => {
    const state = parseCnUrlState(
      new URLSearchParams("platform=kick&page=3&panel=edit&account=abc"),
    );
    expect(state).toEqual({
      platform: "kick",
      page: 3,
      panel: "edit",
      account: "abc",
    });
  });

  it("treats tiktok and unknown platforms as all", () => {
    expect(parseCnUrlState(new URLSearchParams("platform=tiktok")).platform).toBe(
      "all",
    );
    expect(parseCnUrlState(new URLSearchParams("platform=foo")).platform).toBe(
      "all",
    );
  });

  it("drops account unless panel is edit", () => {
    const state = parseCnUrlState(
      new URLSearchParams("panel=templates&account=abc"),
    );
    expect(state.panel).toBe("templates");
    expect(state.account).toBeNull();
  });

  it("resets page to 1 when the platform filter changes", () => {
    const next = withCnPlatform(
      { platform: "youtube", page: 4, panel: null, account: null },
      "twitch",
    );
    expect(next.platform).toBe("twitch");
    expect(next.page).toBe(1);
  });

  it("clamps page when offset would exceed total", () => {
    expect(clampPage(9, 12, 10)).toBe(2);
    expect(clampPage(0, 12, 10)).toBe(1);
    expect(clampPage(1, 0, 10)).toBe(1);
  });

  it("serializes omitted defaults", () => {
    expect(
      serializeCnUrlState({
        platform: "all",
        page: 1,
        panel: null,
        account: null,
      }),
    ).toBe("");
    expect(
      serializeCnUrlState({
        platform: "x",
        page: 2,
        panel: "analytics",
        account: null,
      }),
    ).toBe("platform=x&page=2&panel=analytics");
  });

  it("builds the accounts list query string", () => {
    expect(accountsListQuery({ platform: "all", limit: 10, offset: 0 })).toBe(
      "limit=10&offset=0",
    );
    expect(
      accountsListQuery({ platform: "youtube", limit: 10, offset: 20 }),
    ).toBe("platform=youtube&limit=10&offset=20");
  });

  it("guards dirty modal close", () => {
    expect(shouldCloseDirtyModal(false, false)).toBe(true);
    expect(shouldCloseDirtyModal(true, false)).toBe(false);
    expect(shouldCloseDirtyModal(true, true)).toBe(true);
  });
});
