import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = resolve(__dirname, "..");
const editorPath = resolve(root, "components/editors/rich-message-editor.tsx");
const globalsPath = resolve(root, "app/globals.css");
const honeypotPath = resolve(root, "components/security/honeypot-panel.tsx");
const campaignPath = resolve(
  root,
  "components/campaigns/campaign-wizard.tsx"
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

describe("TinyMCE native resize", () => {
  it("uses vertical-only statusbar resize and does not clip the handle", () => {
    const src = readFileSync(editorPath, "utf8");
    expect(src).toContain("statusbar: true");
    expect(src).toContain("resize: true");
    expect(src).toContain("min_height: height");
    expect(src).not.toContain("min_width:");
    expect(src).toContain("norgoth-rich-editor");
    expect(src).not.toContain("overflow-hidden");
  });

  it("lets the embed modal scroll instead of clipping stacked previews", () => {
    const css = readFileSync(globalsPath, "utf8");
    expect(css).toMatch(
      /\.norgoth-embed-create-modal-body\s*\{[^}]*overflow-y:\s*auto/s
    );
    expect(css).toMatch(/\.prose-preview\s*\{[^}]*overflow:\s*visible/s);
    expect(css).toContain(".norgoth-rich-editor .tox-tinymce");
    expect(css).toContain(".norgoth-rich-editor .tox-statusbar__resize-handle");
    expect(css).toContain("touch-action: none");
    expect(css).not.toContain(".norgoth-rich-editor .tox-edit-area iframe");
    expect(css).not.toContain("resize: vertical");
    expect(css).not.toMatch(
      /\.norgoth-embed-creator-preview\s*\{[^}]*position:\s*sticky/s
    );
  });
});
