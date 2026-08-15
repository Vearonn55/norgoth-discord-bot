import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  colorToHex,
  composeCategoryName,
  composeChannelName,
  hexToColor,
  sanitizeChannelName,
  splitEmojiName,
} from "@/lib/logging";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";

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

describe("composeChannelName", () => {
  it("joins emoji directly to sanitized text with no separator", () => {
    expect(composeChannelName("🔥", "Chat Logs")).toBe("🔥chat-logs");
  });

  it("preserves multi-word hyphenation inside the textual part", () => {
    expect(composeChannelName("💬", "general chat logs")).toBe(
      "💬general-chat-logs"
    );
  });

  it("preserves multi-codepoint / skin-tone / ZWJ emoji intact", () => {
    // Skin-tone modifier sequence
    expect(composeChannelName("👍🏻", "chat logs")).toBe("👍🏻chat-logs");
    // ZWJ family sequence
    expect(composeChannelName("👨‍👩‍👧", "member log")).toBe("👨‍👩‍👧member-log");
  });

  it("returns sanitized name alone when emoji is empty", () => {
    expect(composeChannelName("", "Chat Logs")).toBe("chat-logs");
  });
});

describe("composeCategoryName", () => {
  it("joins emoji to category name with a single space", () => {
    expect(composeCategoryName("📋", "NorBot Logs")).toBe("📋 NorBot Logs");
  });

  it("returns the name alone when emoji is empty", () => {
    expect(composeCategoryName("", "NorBot Logs")).toBe("NorBot Logs");
  });

  it("falls back to NorBot Logs when the name is empty", () => {
    expect(composeCategoryName("", "")).toBe("NorBot Logs");
    expect(composeCategoryName("", "   ")).toBe("NorBot Logs");
  });
});

describe("splitEmojiName", () => {
  it("splits the canonical no-separator form", () => {
    expect(splitEmojiName("🔥chat-logs")).toEqual({
      emoji: "🔥",
      name: "chat-logs",
    });
  });

  it("splits the legacy Discord-hyphenated form", () => {
    expect(splitEmojiName("🔥-chat-logs")).toEqual({
      emoji: "🔥",
      name: "chat-logs",
    });
  });

  it("returns empty emoji when the name has no leading emoji", () => {
    expect(splitEmojiName("chat-logs")).toEqual({
      emoji: "",
      name: "chat-logs",
    });
  });
});

function collectStrings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (value && typeof value === "object") {
    return Object.values(value).flatMap(collectStrings);
  }
  return [];
}

describe("Discord Logs branding copy", () => {
  it("uses NorBot in English and Turkish wizard copy", () => {
    expect(en.discordLogsPage.willCreateCategory).toBe(
      'NorBot will create "{name}".',
    );
    expect(tr.discordLogsPage.willCreateCategory).toBe(
      'NorBot "{name}" oluşturacak.',
    );
    expect(en.discordLogsPage.createManagedCategory).toContain("NorBot");
    expect(tr.discordLogsPage.createManagedCategory).toContain("NorBot");
    expect(en.discordLogsPage.createManagedCategoryHelp).toContain("NorBot");
    expect(tr.discordLogsPage.createManagedCategoryHelp).toContain("NorBot");
    expect(en.discordLogsPage.resetDeleteDiscord).toContain("NorBot");
    expect(tr.discordLogsPage.resetDeleteDiscord).toContain("NorBot");
  });

  it("has no user-facing Norgoth in discordLogsPage copy", () => {
    for (const text of collectStrings(en.discordLogsPage)) {
      expect(text).not.toMatch(/Norgoth/);
    }
    for (const text of collectStrings(tr.discordLogsPage)) {
      expect(text).not.toMatch(/Norgoth/);
    }
  });

  it("keeps NorBot in wizard and logging store user-facing strings", () => {
    const wizard = readFileSync(
      resolve(__dirname, "../components/security/logging-setup-wizard.tsx"),
      "utf8",
    );
    const store = readFileSync(
      resolve(__dirname, "../stores/logging-config-store.ts"),
      "utf8",
    );
    expect(wizard).toContain('useState("NorBot Logs")');
    expect(wizard).not.toMatch(/Norgoth/);
    expect(store).toContain("Could not reach the NorBot API.");
    expect(store).not.toMatch(/Norgoth API/);
  });
});
