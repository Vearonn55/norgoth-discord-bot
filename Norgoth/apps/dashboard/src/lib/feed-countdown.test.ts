import { describe, expect, it } from "vitest";
import { formatCountdown, msUntil } from "@/lib/feed-countdown";

describe("feed countdown helpers", () => {
  it("formats HH:MM:SS", () => {
    expect(formatCountdown(0)).toBe("00:00:00");
    expect(formatCountdown(14 * 60 * 1000 + 32 * 1000)).toBe("00:14:32");
    expect(formatCountdown(3661 * 1000)).toBe("01:01:01");
  });

  it("computes ms until ISO without drifting from render alone", () => {
    const now = Date.parse("2026-08-10T12:00:00Z");
    expect(msUntil("2026-08-10T12:15:00Z", now)).toBe(15 * 60 * 1000);
    expect(msUntil(null, now)).toBe(0);
  });
});
