import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { avatarFallbackLabel } from "@/components/content-notifications/platform-avatar";

describe("PlatformAvatar", () => {
  it("builds initials plus platform letter for the fallback", () => {
    expect(avatarFallbackLabel("Norgoth", "youtube")).toBe("NY");
    expect(avatarFallbackLabel("  ", "twitch")).toBe("?T");
  });

  it("falls back on image error", () => {
    const src = readFileSync(
      resolve(__dirname, "platform-avatar.tsx"),
      "utf8",
    );
    expect(src).toContain("onError");
    expect(src).toContain("alt={displayName}");
  });
});
