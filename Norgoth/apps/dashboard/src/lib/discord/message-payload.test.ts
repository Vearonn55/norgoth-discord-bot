import { describe, expect, it } from "vitest";
import { webhookEmbedToPreview } from "@/lib/discord/message-payload";

describe("webhookEmbedToPreview", () => {
  it("maps Discord webhook embed fields onto the preview payload", () => {
    const mapped = webhookEmbedToPreview({
      title: "Live now",
      description: "Playing",
      color: 0x9146ff,
      footer: { text: "Twitch", icon_url: "https://cdn.example/f.png" },
      author: { name: "Creator", icon_url: "https://cdn.example/a.png" },
      thumbnail: { url: "https://cdn.example/t.png" },
      image: { url: "https://cdn.example/i.png" },
      fields: [{ name: "Category", value: "Just Chatting", inline: true }],
    });
    expect(mapped).toEqual({
      title: "Live now",
      description: "Playing",
      color: 0x9146ff,
      footer: "Twitch",
      footer_icon_url: "https://cdn.example/f.png",
      author: { name: "Creator", icon_url: "https://cdn.example/a.png" },
      thumbnail_url: "https://cdn.example/t.png",
      image_url: "https://cdn.example/i.png",
      fields: [{ name: "Category", value: "Just Chatting", inline: true }],
    });
  });

  it("returns null for a missing embed", () => {
    expect(webhookEmbedToPreview(undefined)).toBeNull();
    expect(webhookEmbedToPreview(null)).toBeNull();
  });
});
