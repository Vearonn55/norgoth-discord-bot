import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("EmbedInstanceSelector unpublished templates", () => {
  it("allows library drafts without a published Discord instance", () => {
    const src = readFileSync(
      resolve(__dirname, "embed-instance-selector.tsx"),
      "utf8"
    );
    expect(src).not.toContain("noPublishedInstance");
    expect(src).not.toContain("publishEmbedFirst");
    expect(src).not.toContain("discord_message_id");
    expect(src).toContain("templateHelp");
  });
});
