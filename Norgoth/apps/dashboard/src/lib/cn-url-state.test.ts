import { describe, expect, it } from "vitest";
import {
  accountEditorSnapshot,
  accountsListQuery,
  clampPage,
  isAccountEditorDirty,
  isTemplateFormDirty,
  parseCnUrlState,
  serializeCnUrlState,
  shouldCloseDirtyModal,
  shouldInvokeModalClose,
  templateFormBaseline,
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

  it("skips CoreUI onExit close when the modal is already hidden or saving", () => {
    expect(shouldInvokeModalClose(true, false)).toBe(true);
    expect(shouldInvokeModalClose(false, false)).toBe(false);
    expect(shouldInvokeModalClose(true, true)).toBe(false);
    expect(shouldCloseDirtyModal(false, false)).toBe(true);
  });

  it("treats a rebased account snapshot as clean after a successful save", () => {
    const saved = accountEditorSnapshot({
      enabled: true,
      channelId: "1",
      roleId: "",
      styleId: "",
      eventTypes: ["VIDEO_PUBLISHED"],
      liveMessage: "hello",
    });
    expect(
      isAccountEditorDirty("edit", saved, saved, {
        url: "",
        channelId: "1",
        liveMessage: "hello",
        defaultLiveMessage: "default",
      }),
    ).toBe(false);
    const edited = accountEditorSnapshot({
      enabled: true,
      channelId: "2",
      roleId: "",
      styleId: "",
      eventTypes: ["VIDEO_PUBLISHED"],
      liveMessage: "hello",
    });
    expect(
      isAccountEditorDirty("edit", saved, edited, {
        url: "",
        channelId: "2",
        liveMessage: "hello",
        defaultLiveMessage: "default",
      }),
    ).toBe(true);
    expect(
      shouldCloseDirtyModal(
        isAccountEditorDirty("edit", saved, saved, {
          url: "",
          channelId: "1",
          liveMessage: "hello",
          defaultLiveMessage: "default",
        }),
        false,
      ),
    ).toBe(true);
  });

  it("keeps failed account saves dirty so the leave warning remains", () => {
    const baseline = accountEditorSnapshot({
      enabled: true,
      channelId: "1",
      roleId: "",
      styleId: "",
      eventTypes: ["VIDEO_PUBLISHED"],
      liveMessage: "hello",
    });
    const dirty = accountEditorSnapshot({
      enabled: false,
      channelId: "1",
      roleId: "",
      styleId: "",
      eventTypes: ["VIDEO_PUBLISHED"],
      liveMessage: "hello",
    });
    expect(
      shouldCloseDirtyModal(
        isAccountEditorDirty("edit", baseline, dirty, {
          url: "",
          channelId: "1",
          liveMessage: "hello",
          defaultLiveMessage: "default",
        }),
        false,
      ),
    ).toBe(false);
  });

  it("does not treat selecting a template card as dirty", () => {
    const template = {
      name: "Default",
      content: "body",
      platform_default_for: "youtube" as string | null,
    };
    const baseline = templateFormBaseline(template, {
      name: "",
      content: "default",
    });
    expect(
      isTemplateFormDirty(
        {
          name: "Default",
          content: "body",
          platformDefault: "youtube",
        },
        baseline,
      ),
    ).toBe(false);
    expect(
      isTemplateFormDirty(
        {
          name: "Default",
          content: "changed",
          platformDefault: "youtube",
        },
        baseline,
      ),
    ).toBe(true);
  });

  it("tracks template and style dirty flags independently", () => {
    const templatesDirty = isTemplateFormDirty(
      { name: "A", content: "x", platformDefault: "" },
      { name: "", content: "x", platformDefault: "" },
    );
    const stylesDirty = false;
    expect(templatesDirty).toBe(true);
    expect(stylesDirty).toBe(false);
    expect(shouldCloseDirtyModal(templatesDirty, false)).toBe(false);
    expect(shouldCloseDirtyModal(stylesDirty, false)).toBe(true);
  });
});
