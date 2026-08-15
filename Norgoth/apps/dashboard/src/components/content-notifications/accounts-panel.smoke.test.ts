import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("AccountsPanel CN preview", () => {
  it("passes webhook embeds into MessagePreview embed mode without placeholders", () => {
    const src = readFileSync(
      resolve(__dirname, "accounts-panel.tsx"),
      "utf8",
    );
    expect(src).toContain("webhookEmbedToPreview");
    expect(src).toContain('mode="embed"');
    expect(src).toContain("showContentWithEmbed");
    expect(src).not.toContain("showImagePlaceholders");
  });
});
