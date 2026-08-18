import { describe, expect, it } from "vitest";
import { compileForPreview, DISCORD_DELIVERY_LIMITS } from "@/lib/discord/message-compiler";

describe("compileForPreview", () => {
  it("returns a single payload for short content", () => {
    const result = compileForPreview("Hello", {
      title: "Title",
      description: "Body",
    });
    expect(result.errors).toHaveLength(0);
    expect(result.payloads).toHaveLength(1);
    expect(result.payloads[0].embeds).toHaveLength(1);
  });

  it("packs a long description into stacked embeds without exceeding 6000 per message", () => {
    const long = "Paragraph.\n\n".repeat(500).trim();
    const result = compileForPreview("", { description: long });
    expect(result.errors).toHaveLength(0);
    const embeds = result.payloads.flatMap((payload) => payload.embeds ?? []);
    expect(embeds.length).toBeGreaterThan(1);
    for (const embed of embeds) {
      expect((embed.description ?? "").length).toBeLessThanOrEqual(
        DISCORD_DELIVERY_LIMITS.embedDescription,
      );
    }
    for (const payload of result.payloads) {
      const total = (payload.embeds ?? []).reduce(
        (sum, embed) =>
          sum +
          (embed.title?.length ?? 0) +
          (embed.description?.length ?? 0) +
          (embed.footer?.length ?? 0) +
          (embed.author?.name?.length ?? 0),
        0,
      );
      expect(total).toBeLessThanOrEqual(DISCORD_DELIVERY_LIMITS.total);
    }
  });

  it("keeps title plus first description under the 6000 total cap", () => {
    const result = compileForPreview("", {
      title: "T".repeat(256),
      footer: "F".repeat(80),
      description: "x".repeat(5000),
    });
    expect(result.errors).toHaveLength(0);
    const first = result.payloads[0].embeds?.[0];
    const total =
      (first?.title?.length ?? 0) +
      (first?.description?.length ?? 0) +
      (first?.footer?.length ?? 0);
    expect(total).toBeLessThanOrEqual(DISCORD_DELIVERY_LIMITS.total);
    const embeds = result.payloads.flatMap((payload) => payload.embeds ?? []);
    expect(embeds.length).toBeGreaterThan(1);
  });

  it("splits three large stacked embeds across messages", () => {
    const long = "Paragraph.\n\n".repeat(800).trim();
    const result = compileForPreview("", { description: long });
    expect(result.errors).toHaveLength(0);
    const embeds = result.payloads.flatMap((payload) => payload.embeds ?? []);
    expect(embeds.length).toBeGreaterThanOrEqual(3);
    expect(result.payloads.length).toBeGreaterThanOrEqual(2);
    for (const payload of result.payloads) {
      const total = (payload.embeds ?? []).reduce(
        (sum, embed) => sum + (embed.description?.length ?? 0),
        0,
      );
      expect(total).toBeLessThanOrEqual(DISCORD_DELIVERY_LIMITS.total);
    }
  });

  it("keeps three small stacked embeds in one message", () => {
    const result = compileForPreview("", {
      description: `${"a".repeat(1500)}\n\n${"b".repeat(1500)}\n\n${"c".repeat(1500)}`,
    });
    expect(result.errors).toHaveLength(0);
    const total = result.payloads.reduce(
      (sum, payload) =>
        sum +
        (payload.embeds ?? []).reduce(
          (inner, embed) => inner + (embed.description?.length ?? 0),
          0,
        ),
      0,
    );
    expect(total).toBeLessThanOrEqual(DISCORD_DELIVERY_LIMITS.total * result.payloads.length);
    for (const payload of result.payloads) {
      const chars = (payload.embeds ?? []).reduce(
        (sum, embed) => sum + (embed.description?.length ?? 0),
        0,
      );
      expect(chars).toBeLessThanOrEqual(DISCORD_DELIVERY_LIMITS.total);
    }
  });
});
