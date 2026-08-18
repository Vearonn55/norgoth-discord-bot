import { describe, expect, it } from "vitest";
import fixtures from "@/lib/discord-markdown.fixtures.json";
import {
  DISCORD_MARKDOWN_SPEC_VERSION,
  discordMarkdownToHtml,
  htmlToDiscordMarkdown,
  isSafeHttpUrl,
} from "@/lib/discord-markdown";

describe("discord-markdown fixtures", () => {
  it("exports a spec version", () => {
    expect(DISCORD_MARKDOWN_SPEC_VERSION).toBe(1);
  });

  for (const fixture of fixtures) {
    it(`renders ${fixture.name}`, () => {
      const html = discordMarkdownToHtml(fixture.markdown);
      for (const needle of fixture.expectContains) {
        expect(html).toContain(needle);
      }
    });
  }
});

describe("htmlToDiscordMarkdown", () => {
  it("preserves list items on separate lines", () => {
    const html = "<ul><li>One</li><li>Two</li></ul>";
    const md = htmlToDiscordMarkdown(html);
    expect(md).toContain("- One");
    expect(md).toContain("- Two");
  });

  it("degrades h4 to bold", () => {
    const md = htmlToDiscordMarkdown("<h4>Sub</h4>");
    expect(md).toContain("**Sub**");
    expect(md).not.toContain("####");
  });

  it("strips unsafe links", () => {
    expect(isSafeHttpUrl("javascript:alert(1)")).toBe(false);
    const md = htmlToDiscordMarkdown(
      '<a href="javascript:alert(1)">bad</a>',
    );
    expect(md).not.toContain("javascript:");
  });
});

describe("round-trip spacing", () => {
  it("keeps paragraph breaks through html conversion", () => {
    const source = "<p>Line A</p><p>Line B</p>";
    const md = htmlToDiscordMarkdown(source);
    const html = discordMarkdownToHtml(md);
    expect(html).toContain("Line A");
    expect(html).toContain("Line B");
    expect(html).toContain("prose-spacer");
  });
});
