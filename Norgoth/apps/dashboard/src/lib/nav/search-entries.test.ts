import { describe, expect, it } from "vitest";
import {
  filterSearchEntries,
  formatSearchEntryLabel,
  getSearchEntries,
} from "@/lib/nav/search-entries";

describe("search entries", () => {
  const entries = getSearchEntries("en");

  it("includes main pages and curated sub-features", () => {
    expect(entries.some((e) => e.label === "Leaderboards")).toBe(true);
    expect(entries.some((e) => e.id === "sub:leaderboard.voice")).toBe(true);
    expect(entries.some((e) => e.id === "sub:discord-logs.invites")).toBe(true);
    expect(entries.some((e) => e.id === "sub:tickets.panels")).toBe(true);
  });

  it("ranks voice xp ahead of weak parent-only hits", () => {
    const filtered = filterSearchEntries(entries, "voice xp");
    expect(filtered[0]?.id).toBe("sub:leaderboard.voice");
    expect(formatSearchEntryLabel(filtered[0]!)).toContain("›");
  });

  it("finds invite logs under Discord Logs", () => {
    const filtered = filterSearchEntries(entries, "invite logs");
    expect(filtered.some((e) => e.id === "sub:discord-logs.invites")).toBe(
      true
    );
  });

  it("finds auto role via alias", () => {
    const filtered = filterSearchEntries(entries, "autorole");
    expect(
      filtered.some(
        (e) =>
          e.href.includes("/automation/auto-role") || e.id === "sub:autorole"
      )
    ).toBe(true);
  });

  it("shows pages only when query is empty", () => {
    const filtered = filterSearchEntries(entries, "");
    expect(filtered.every((e) => e.kind === "page")).toBe(true);
  });

  it("still finds Automation pages and subfeatures after the category reorder", () => {
    expect(entries.some((e) => e.id === "page:automation.auto-role")).toBe(true);
    expect(entries.some((e) => e.id === "sub:autorole")).toBe(true);
    expect(entries.some((e) => e.id === "sub:welcome")).toBe(true);
    const filtered = filterSearchEntries(entries, "automation");
    expect(
      filtered.some((e) => e.href.includes("/automation/auto-role")),
    ).toBe(true);
  });

  it("places RSS Feeds under Automation in search without duplicating the page", () => {
    const rssPages = entries.filter((e) => e.id === "page:messages.rss-feeds");
    expect(rssPages).toHaveLength(1);
    expect(rssPages[0]?.href).toBe("/en/messages/rss-feeds");
    expect(rssPages[0]?.group).toBe("AUTOMATION");

    const addFeed = entries.find((e) => e.id === "sub:rss-feeds.add");
    expect(addFeed?.href).toBe("/en/messages/rss-feeds");
    expect(addFeed?.group).toBe("AUTOMATION");
    expect(addFeed?.parentId).toBe("page:messages.rss-feeds");

    const filtered = filterSearchEntries(entries, "rss");
    expect(filtered.some((e) => e.id === "page:messages.rss-feeds")).toBe(true);
    expect(filtered.filter((e) => e.href.endsWith("/messages/rss-feeds")).length).toBeGreaterThan(
      0,
    );

    const trEntries = getSearchEntries("tr");
    const trRss = trEntries.find((e) => e.id === "page:messages.rss-feeds");
    expect(trRss?.group).toBe("OTOMASYON");
    expect(trRss?.href).toBe("/tr/messages/rss-feeds");
    expect(
      filterSearchEntries(trEntries, "rss akış").some(
        (e) => e.id === "page:messages.rss-feeds",
      ),
    ).toBe(true);
  });
});
