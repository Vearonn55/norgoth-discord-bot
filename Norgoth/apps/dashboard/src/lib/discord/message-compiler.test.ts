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

  it("packs a long description into stacked embeds in one message", () => {
    const long = "Paragraph.\n\n".repeat(500).trim();
    const result = compileForPreview("", { description: long });
    expect(result.errors).toHaveLength(0);
    expect(result.payloads).toHaveLength(1);
    expect((result.payloads[0].embeds ?? []).length).toBeGreaterThan(1);
    for (const embed of result.payloads[0].embeds ?? []) {
      expect((embed.description ?? "").length).toBeLessThanOrEqual(
        DISCORD_DELIVERY_LIMITS.embedDescription,
      );
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
    expect((result.payloads[0].embeds ?? []).length).toBeGreaterThan(1);
  });
});
