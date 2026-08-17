import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";

describe("RSS feeds dashboard copy", () => {
  it("interpolates capacity and maps probe error codes", () => {
    expect(en.rssFeedsPage.infoBanner).toContain("{max}");
    expect(tr.rssFeedsPage.infoBanner).toContain("{max}");
    expect(en.rssFeedsPage.probeInvalidDocument).toBeTruthy();
    expect(tr.rssFeedsPage.probeInvalidDocument).toBeTruthy();
    expect(en.rssFeedsPage.limitReached).toBeTruthy();
    const panel = readFileSync(
      resolve(__dirname, "rss-feeds-panel.tsx"),
      "utf8",
    );
    expect(panel).toContain("rssErrorMessage");
    expect(panel).toContain("formatDict(d.infoBanner");
    expect(panel).toContain("emptyFeedWarning");
    const store = readFileSync(
      resolve(__dirname, "../../stores/rss-feeds-store.ts"),
      "utf8",
    );
    expect(store).toContain("maxFeeds: 15");
    expect(store).toContain("error_code");
  });
});
