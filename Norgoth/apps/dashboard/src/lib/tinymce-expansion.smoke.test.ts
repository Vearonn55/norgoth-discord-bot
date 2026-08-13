import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = resolve(__dirname, "..");
const honeypotPath = resolve(root, "components/security/honeypot-panel.tsx");
const campaignPath = resolve(
  root,
  "components/campaigns/campaign-create-wizard.tsx"
);
const leaderboardPath = resolve(
  root,
  "components/community/leaderboard-panel.tsx"
);

describe("honeypot TinyMCE + Embed Creator", () => {
  it("uses RichMessageEditor for content and embed description", () => {
    const src = readFileSync(honeypotPath, "utf8");
    expect(src).toContain("RichMessageEditor");
    expect(src).toContain("honeypot-content-");
    expect(src).toContain("honeypot-desc-");
    expect(src).toContain("hideDescription");
    expect(src).toContain("d.selectFromDraft");
    expect(src).toContain("d.createNew");
    expect(src).toContain("EmbedDraftCreator");
  });
});

describe("campaign internal description TinyMCE", () => {
  it("uses RichMessageEditor for Internal Description on step 1", () => {
    const src = readFileSync(campaignPath, "utf8");
    expect(src).toContain("RichMessageEditor");
    expect(src).toContain("campaign-internal-desc");
  });
});

describe("leaderboard Top Upvote label", () => {
  it("shows Top Upvote and keeps net_upvotes metric id", () => {
    const src = readFileSync(leaderboardPath, "utf8");
    expect(src).toContain('id: "net_upvotes"');
    expect(src).toContain("label: d.tabNetUpvotes");
    expect(src).toContain("d.tabNetUpvotes");
    expect(src).not.toContain("Top Net Upvote");
  });
});
