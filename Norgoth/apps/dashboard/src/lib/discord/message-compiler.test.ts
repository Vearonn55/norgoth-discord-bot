import { describe, expect, it } from "vitest";
import { compileForPreview } from "@/lib/discord/message-compiler";

describe("compileForPreview", () => {
  it("returns a single payload for short content", () => {
    const result = compileForPreview("Hello", {
      title: "Title",
      description: "Body",
    });
    expect(result.errors).toHaveLength(0);
    expect(result.payloads).toHaveLength(1);
  });

  it("splits very long descriptions into multiple preview payloads", () => {
    const long = "Paragraph.\n\n".repeat(500).trim();
    const result = compileForPreview("", { description: long });
    expect(result.errors).toHaveLength(0);
    expect(result.payloads.length).toBeGreaterThan(1);
  });
});
