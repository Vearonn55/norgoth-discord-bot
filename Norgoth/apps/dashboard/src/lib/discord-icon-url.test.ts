import { describe, expect, it } from "vitest";
import { discordIconUrl } from "./discord-icon-url";

describe("discordIconUrl", () => {
  it("uses gif for animated hashes and png otherwise", () => {
    expect(discordIconUrl("111", "a_abc123", 128)).toBe(
      "https://cdn.discordapp.com/icons/111/a_abc123.gif?size=128",
    );
    expect(discordIconUrl("111", "abc123", 64)).toBe(
      "https://cdn.discordapp.com/icons/111/abc123.png?size=64",
    );
  });

  it("returns null when the hash is missing", () => {
    expect(discordIconUrl("111", null)).toBeNull();
    expect(discordIconUrl("111", undefined)).toBeNull();
    expect(discordIconUrl("", "abc")).toBeNull();
  });
});
