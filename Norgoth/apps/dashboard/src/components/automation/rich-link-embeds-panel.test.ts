import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";
import { previewRewrite } from "@/lib/rich-link-embeds-preview";
import {
  FIXED_REWRITE_HOSTS,
  defaults,
} from "@/stores/rich-link-embeds-store";

describe("Link Embeds dashboard", () => {
  it("uses six platforms and tnktok.com", () => {
    expect(Object.keys(FIXED_REWRITE_HOSTS)).toEqual([
      "twitter",
      "tiktok",
      "instagram",
      "reddit",
      "pixiv",
      "youtube_shorts",
    ]);
    expect(FIXED_REWRITE_HOSTS.tiktok).toBe("tnktok.com");
    expect("bluesky" in defaults.platforms).toBe(false);
    expect("platformDescBluesky" in en.richLinkEmbedsPage).toBe(false);
    expect("platformDescBluesky" in tr.richLinkEmbedsPage).toBe(false);
    expect(en.featureInfo.richLinkEmbeds.description).not.toMatch(/Bluesky/i);
    expect(tr.featureInfo.richLinkEmbeds.description).not.toMatch(/Bluesky/i);
  });

  it("previews TikTok rewrites and leaves Bluesky untouched", () => {
    const config = defaults;
    expect(
      previewRewrite("https://www.tiktok.com/@c/video/9", {
        ...config,
        platforms: { ...config.platforms, tiktok: true },
      }),
    ).toBe("https://tnktok.com/@c/video/9");
    expect(
      previewRewrite(
        "https://bsky.app/profile/alice.bsky.social/post/abc123",
        config,
      ),
    ).toBeNull();
  });

  it("lays out platform cards in an equal-height grid", () => {
    const panel = readFileSync(
      resolve(__dirname, "rich-link-embeds-panel.tsx"),
      "utf8",
    );
    expect(panel).toContain("norgoth-link-embeds-grid");
    expect(panel).not.toContain("platformDescBluesky");
    expect(panel).not.toContain("bskx.app");
  });
});
