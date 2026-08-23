import { describe, expect, it } from "vitest";
import {
  DISCORD_DEFAULT_ROLE_COLOR,
  discordRoleDotColor,
  discordRoleTextColor,
  isDiscordDefaultRoleColor,
  normalizeDiscordRoleColor,
  roleColorStyles,
} from "@/lib/discord/role-color";

describe("isDiscordDefaultRoleColor", () => {
  it("treats Discord sentinel and legacy #000000 as default", () => {
    expect(isDiscordDefaultRoleColor(0)).toBe(true);
    expect(isDiscordDefaultRoleColor("0")).toBe(true);
    expect(isDiscordDefaultRoleColor(null)).toBe(true);
    expect(isDiscordDefaultRoleColor("#000000")).toBe(true);
    expect(isDiscordDefaultRoleColor("000000")).toBe(true);
  });

  it("does not treat nonzero colors as default", () => {
    expect(isDiscordDefaultRoleColor(255)).toBe(false);
    expect(isDiscordDefaultRoleColor("#ff0000")).toBe(false);
  });
});

describe("normalizeDiscordRoleColor", () => {
  it("returns null for default sentinel values", () => {
    expect(normalizeDiscordRoleColor(0)).toBeNull();
    expect(normalizeDiscordRoleColor("#000000")).toBeNull();
  });

  it("preserves leading zeroes for valid nonzero colors", () => {
    expect(normalizeDiscordRoleColor(255)).toBe("#0000ff");
    expect(normalizeDiscordRoleColor(16711680)).toBe("#ff0000");
    expect(normalizeDiscordRoleColor("#2ecc71")).toBe("#2ecc71");
  });

  it("returns null for malformed values", () => {
    expect(normalizeDiscordRoleColor("not-a-color")).toBeNull();
    expect(normalizeDiscordRoleColor("#abc")).toBeNull();
  });
});

describe("discordRoleDotColor", () => {
  it("maps default sentinel to Discord gray", () => {
    expect(discordRoleDotColor(0)).toBe(DISCORD_DEFAULT_ROLE_COLOR);
    expect(discordRoleDotColor("#000000")).toBe(DISCORD_DEFAULT_ROLE_COLOR);
  });

  it("returns accurate hex for custom colors", () => {
    expect(discordRoleDotColor(3066993)).toBe("#2ecc71");
  });

  it("uses neutral fallback for malformed values", () => {
    expect(discordRoleDotColor("???")).toBe(DISCORD_DEFAULT_ROLE_COLOR);
  });
});

describe("discordRoleTextColor", () => {
  it("matches dot color semantics", () => {
    expect(discordRoleTextColor(0)).toBe(DISCORD_DEFAULT_ROLE_COLOR);
    expect(discordRoleTextColor(255)).toBe("#0000ff");
  });
});

describe("roleColorStyles", () => {
  it("returns tinted styles for default roles", () => {
    const styles = roleColorStyles(0);
    expect(styles.background).toBe(`${DISCORD_DEFAULT_ROLE_COLOR}33`);
    expect(styles.borderColor).toBe(`${DISCORD_DEFAULT_ROLE_COLOR}99`);
  });

  it("returns tinted styles for explicit colors", () => {
    const styles = roleColorStyles("#ff0000");
    expect(styles.background).toBe("#ff000033");
  });
});
