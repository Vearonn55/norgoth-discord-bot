import { describe, expect, it } from "vitest";
import { colorToHex, hexToColor, sanitizeChannelName } from "@/lib/logging";

describe("colorToHex", () => {
  it("formats a decimal colour as #RRGGBB", () => {
    expect(colorToHex(0x5865f2)).toBe("#5865f2");
    expect(colorToHex(0x000000)).toBe("#000000");
    expect(colorToHex(0xffffff)).toBe("#ffffff");
  });

  it("falls back to blurple for null/undefined", () => {
    expect(colorToHex(null)).toBe("#5865f2");
    expect(colorToHex(undefined)).toBe("#5865f2");
  });
});

describe("hexToColor", () => {
  it("parses valid hex with and without the leading #", () => {
    expect(hexToColor("#5865f2")).toBe(0x5865f2);
    expect(hexToColor("5865f2")).toBe(0x5865f2);
  });

  it("returns null for invalid input", () => {
    expect(hexToColor("nothex")).toBeNull();
    expect(hexToColor("#12345")).toBeNull();
    expect(hexToColor("")).toBeNull();
  });

  it("round-trips with colorToHex", () => {
    expect(colorToHex(hexToColor("#1abc9c"))).toBe("#1abc9c");
  });
});

describe("sanitizeChannelName", () => {
  it("lowercases and hyphenates spaces", () => {
    expect(sanitizeChannelName("Member Log")).toBe("member-log");
  });

  it("strips invalid characters", () => {
    expect(sanitizeChannelName("Mod #Log! (2024)")).toBe("mod-log-2024");
  });

  it("falls back to 'log' when nothing usable remains", () => {
    expect(sanitizeChannelName("!!!")).toBe("log");
    expect(sanitizeChannelName("")).toBe("log");
  });

  it("caps length at 90 characters", () => {
    expect(sanitizeChannelName("a".repeat(200)).length).toBe(90);
  });
});
