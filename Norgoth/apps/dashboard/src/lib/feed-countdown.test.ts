import { describe, expect, it } from "vitest";
import {
  COUNTDOWN_PLACEHOLDER,
  formatCountdown,
  msUntil,
  snapshotRemainingMs,
  type CountdownSnapshot,
} from "@/lib/feed-countdown";

describe("feed countdown helpers", () => {
  it("formats HH:MM:SS", () => {
    expect(formatCountdown(0)).toBe("00:00:00");
    expect(formatCountdown(14 * 60 * 1000 + 32 * 1000)).toBe("00:14:32");
    expect(formatCountdown(3661 * 1000)).toBe("01:01:01");
  });

  it("computes remaining from next_refresh_at timestamp", () => {
    const now = Date.parse("2026-08-10T12:00:00Z");
    expect(msUntil("2026-08-10T12:05:00Z", now)).toBe(5 * 60 * 1000);
    expect(formatCountdown(msUntil("2026-08-10T12:05:00Z", now))).toBe(
      "00:05:00"
    );
  });

  it("ticks from backend remaining_seconds snapshot (skew-safe)", () => {
    const snapshot: CountdownSnapshot = {
      remainingSeconds: 600,
      serverTime: "2026-08-10T14:00:00Z",
      nextRefreshAt: "2026-08-10T14:10:00Z",
      receivedAt: Date.parse("2026-08-10T14:00:00Z"),
    };
    expect(
      formatCountdown(
        snapshotRemainingMs(snapshot, Date.parse("2026-08-10T14:00:00Z"))
      )
    ).toBe("00:10:00");
    expect(
      formatCountdown(
        snapshotRemainingMs(snapshot, Date.parse("2026-08-10T14:05:00Z"))
      )
    ).toBe("00:05:00");
  });

  it("does not invent full slider minutes when remaining is known", () => {
    const snapshot: CountdownSnapshot = {
      remainingSeconds: 90,
      serverTime: "2026-08-10T14:00:00Z",
      nextRefreshAt: "2026-08-10T14:01:30Z",
      receivedAt: Date.parse("2026-08-10T14:00:00Z"),
    };
    // Slider may be 30m; display must follow remaining_seconds (90s).
    expect(
      formatCountdown(
        snapshotRemainingMs(snapshot, Date.parse("2026-08-10T14:00:00Z"))
      )
    ).toBe("00:01:30");
  });

  it("corrects after clock jump (tab sleep model)", () => {
    const next = "2026-08-10T14:10:00Z";
    const atOpen = Date.parse("2026-08-10T14:00:00Z");
    const afterSleep = Date.parse("2026-08-10T14:05:00Z");
    expect(formatCountdown(Math.max(0, msUntil(next, atOpen)))).toBe(
      "00:10:00"
    );
    expect(formatCountdown(Math.max(0, msUntil(next, afterSleep)))).toBe(
      "00:05:00"
    );
  });

  it("holds at zero when overdue until backend advances", () => {
    const snapshot: CountdownSnapshot = {
      remainingSeconds: 0,
      serverTime: "2026-08-10T12:01:00Z",
      nextRefreshAt: "2026-08-10T12:00:00Z",
      receivedAt: Date.parse("2026-08-10T12:01:00Z"),
    };
    expect(snapshotRemainingMs(snapshot)).toBe(0);
    expect(formatCountdown(0)).toBe("00:00:00");
  });

  it("exposes placeholder for unknown schedule", () => {
    expect(COUNTDOWN_PLACEHOLDER).toBe("--:--:--");
    expect(msUntil(null)).toBe(0);
    expect(snapshotRemainingMs(null)).toBe(0);
  });
});
