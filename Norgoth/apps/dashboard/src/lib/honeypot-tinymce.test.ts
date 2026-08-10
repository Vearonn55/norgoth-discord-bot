import { describe, expect, it } from "vitest";
import {
  assertDiscordMarkdownLength,
  isBlankDiscordMarkdown,
} from "@/lib/discord-markdown-validation";
import { copyEmbedIntoHoneypot } from "@/lib/honeypot-embed-copy";
import type { EmbedMessage } from "@/stores/embed-messages-store";

describe("discord markdown validation", () => {
  it("treats empty TinyMCE scaffolding as blank", () => {
    expect(isBlankDiscordMarkdown("")).toBe(true);
    expect(isBlankDiscordMarkdown("   ")).toBe(true);
    expect(isBlankDiscordMarkdown("\n\n")).toBe(true);
  });

  it("accepts meaningful markdown within length", () => {
    expect(assertDiscordMarkdownLength("**hi**", 1000)).toEqual({
      ok: true,
      trimmed: "**hi**",
    });
  });

  it("rejects over-length markdown", () => {
    expect(assertDiscordMarkdownLength("x".repeat(1001), 1000).reason).toBe(
      "too_long"
    );
  });
});

describe("honeypot embed library copy", () => {
  it("copies draft content and embed_json into warning snapshot", () => {
    const draft = {
      id: "d1",
      guild_id: "g1",
      name: "Warn",
      description: "",
      content: "Do not post here",
      embed_json: {
        title: "Trap",
        description: "Bots only",
        color: "#ff9900",
        fields: [{ name: "A", value: "B", inline: false }],
      },
      version: 1,
      created_at: "",
      updated_at: "",
    } as EmbedMessage;

    expect(copyEmbedIntoHoneypot(draft)).toEqual({
      warning_content: "Do not post here",
      warning_embed: {
        title: "Trap",
        description: "Bots only",
        color: "#ff9900",
        fields: [{ name: "A", value: "B", inline: false }],
      },
    });
  });

  it("does not keep a live reference — snapshot is a shallow copy", () => {
    const embed = { title: "T", description: "D" };
    const draft = {
      id: "d2",
      content: "c",
      embed_json: embed,
    } as EmbedMessage;
    const copied = copyEmbedIntoHoneypot(draft);
    embed.title = "mutated";
    expect((copied.warning_embed as { title: string }).title).toBe("T");
  });
});
