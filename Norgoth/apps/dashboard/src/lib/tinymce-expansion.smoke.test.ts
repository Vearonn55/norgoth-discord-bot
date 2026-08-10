import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const honeypotPath = resolve(
  __dirname,
  "../components/security/honeypot-panel.tsx"
);
const leaderboardPath = resolve(
  __dirname,
  "../components/community/leaderboard-panel.tsx"
);
const campaignPath = resolve(
  __dirname,
  "../components/campaigns/campaign-wizard.tsx"
);

describe("honeypot TinyMCE + Embed Creator", () => {
  it("uses RichMessageEditor for content and embed description", () => {
    const src = readFileSync(honeypotPath, "utf8");
    expect(src).toContain("RichMessageEditor");
    expect(src).toContain("honeypot-content-");
    expect(src).toContain("honeypot-desc-");
    expect(src).toContain("hideDescription");
    expect(src).toContain("Select From Draft");
    expect(src).toContain("Create New");
    expect(src).toContain("EmbedDraftCreator");
    expect(src).toContain("copyEmbedIntoHoneypot");
    expect(src).toContain("@/lib/honeypot-embed-copy");
    expect(src).not.toMatch(/CFormTextarea/);
  });
});

describe("leaderboard Top Upvote label", () => {
  it("shows Top Upvote and keeps net_upvotes metric id", () => {
    const src = readFileSync(leaderboardPath, "utf8");
    expect(src).toContain('id: "net_upvotes"');
    expect(src).toContain('label: "Top Upvote"');
    expect(src).toContain('"Top Upvote"');
    expect(src).not.toContain("Top Net Upvote");
  });
});

describe("campaign internal description TinyMCE", () => {
  it("uses RichMessageEditor for Internal Description on step 1", () => {
    const src = readFileSync(campaignPath, "utf8");
    expect(src).toContain("campaign-internal-desc-");
    expect(src).toContain("internalDescription");
    expect(src).toContain("isBlankDiscordMarkdown");
    expect(src).toContain("description: payload.description");
  });
});
