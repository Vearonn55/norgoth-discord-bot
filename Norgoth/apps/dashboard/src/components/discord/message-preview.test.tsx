import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MessagePreview } from "@/components/discord/message-preview";

describe("MessagePreview modes", () => {
  it("text mode never renders an embed card", () => {
    const html = renderToStaticMarkup(
      <MessagePreview
        mode="text"
        content="Hello"
        embed={{ title: "Embed", description: "Body" }}
        showEmbed
      />
    );
    expect(html).toContain("Hello");
    expect(html).not.toContain("norgoth-discord-embed");
  });

  it("embed mode hides empty plain-text placeholder", () => {
    const html = renderToStaticMarkup(
      <MessagePreview
        mode="embed"
        embed={{ title: "Level up", description: "Nice work" }}
      />
    );
    expect(html).not.toContain("No message content");
    expect(html).toContain("Level up");
    expect(html).toContain("norgoth-discord-embed");
  });

  it("embed mode with showContentWithEmbed shows non-empty content only", () => {
    const withContent = renderToStaticMarkup(
      <MessagePreview
        mode="embed"
        showContentWithEmbed
        content="Above"
        embed={{ title: "T", description: "D" }}
      />
    );
    expect(withContent).toContain("Above");

    const empty = renderToStaticMarkup(
      <MessagePreview
        mode="embed"
        showContentWithEmbed
        content="   "
        embed={{ title: "T", description: "D" }}
      />
    );
    expect(empty).not.toContain("No message content");
  });
});
