import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MessagePreview } from "@/components/discord/message-preview";
import { scrubEmptyEmbedUrls } from "@/lib/discord/message-payload";

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

describe("MessagePreview image placeholders", () => {
  const baseEmbed = {
    title: "Title",
    description: "Body",
    author: { name: "Author" },
    footer: "Footer",
  };

  it("does not render placeholders by default", () => {
    const html = renderToStaticMarkup(
      <MessagePreview mode="embed" embed={baseEmbed} />
    );
    expect(html).not.toContain("norgoth-embed-placeholder");
    expect(html).not.toContain("norgoth-embed-icon-placeholder");
    expect(html).not.toContain("https://");
  });

  it("renders author/thumbnail/image/footer placeholders when enabled", () => {
    const html = renderToStaticMarkup(
      <MessagePreview mode="embed" embed={baseEmbed} showImagePlaceholders />
    );
    expect(html).toContain("norgoth-embed-placeholder");
    expect(html).toContain("Thumbnail");
    expect(html).toContain("Main image");
    expect(html).toContain("norgoth-embed-icon-placeholder");
    expect(html).toContain("Author icon");
    expect(html).toContain("Footer icon");
  });

  it("does not mutate embed URLs when placeholders are shown", () => {
    const embed = { ...baseEmbed };
    renderToStaticMarkup(
      <MessagePreview mode="embed" embed={embed} showImagePlaceholders />
    );
    expect(embed.thumbnail_url).toBeUndefined();
    expect(embed.image_url).toBeUndefined();
    expect(embed.footer_icon_url).toBeUndefined();
    expect(embed.author?.icon_url).toBeUndefined();
  });

  it("replaces placeholders with real media URLs", () => {
    const html = renderToStaticMarkup(
      <MessagePreview
        mode="embed"
        showImagePlaceholders
        embed={{
          ...baseEmbed,
          author: { name: "Author", icon_url: "https://cdn.example/a.png" },
          thumbnail_url: "https://cdn.example/t.png",
          image_url: "https://cdn.example/i.png",
          footer_icon_url: "https://cdn.example/f.png",
        }}
      />
    );
    expect(html).toContain("https://cdn.example/a.png");
    expect(html).toContain("https://cdn.example/t.png");
    expect(html).toContain("https://cdn.example/i.png");
    expect(html).toContain("https://cdn.example/f.png");
    expect(html).not.toContain("norgoth-embed-placeholder");
    expect(html).not.toContain("norgoth-embed-icon-placeholder");
  });
});

describe("scrubEmptyEmbedUrls", () => {
  it("omits empty and whitespace image fields", () => {
    const scrubbed = scrubEmptyEmbedUrls({
      title: "T",
      thumbnail_url: "  ",
      image_url: "",
      footer_icon_url: "\t",
      author: { name: "A", icon_url: " ", url: "https://ok.example" },
    });
    expect(scrubbed.thumbnail_url).toBeUndefined();
    expect(scrubbed.image_url).toBeUndefined();
    expect(scrubbed.footer_icon_url).toBeUndefined();
    expect(scrubbed.author?.icon_url).toBeUndefined();
    expect(scrubbed.author?.url).toBe("https://ok.example");
  });
});
