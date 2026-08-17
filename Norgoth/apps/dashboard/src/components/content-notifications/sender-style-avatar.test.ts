import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  isPublicHttpsAvatarUrl,
  senderStyleFallbackLabel,
} from "@/components/content-notifications/sender-style-avatar";

describe("SenderStyleAvatar URL checks", () => {
  it("accepts empty and public https, rejects unsafe schemes and private hosts", () => {
    expect(isPublicHttpsAvatarUrl("")).toBe(true);
    expect(isPublicHttpsAvatarUrl("https://cdn.discordapp.com/a.png")).toBe(true);
    expect(isPublicHttpsAvatarUrl("javascript:alert(1)")).toBe(false);
    expect(isPublicHttpsAvatarUrl("http://cdn.example.com/a.png")).toBe(false);
    expect(isPublicHttpsAvatarUrl("https://user:pass@cdn.example.com/a.png")).toBe(
      false,
    );
    expect(isPublicHttpsAvatarUrl("https://127.0.0.1/a.png")).toBe(false);
    expect(senderStyleFallbackLabel("Norgoth")).toBe("N");
  });

  it("uses a native img with onError and no-referrer", () => {
    const src = readFileSync(
      resolve(__dirname, "sender-style-avatar.tsx"),
      "utf8",
    );
    expect(src).toContain("onError");
    expect(src).toContain('referrerPolicy="no-referrer"');
    expect(src).not.toContain("next/image");
  });
});
