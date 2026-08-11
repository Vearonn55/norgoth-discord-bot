import { describe, expect, it } from "vitest";
import {
  DEFAULT_LEVELING_CONFIG,
  VOICE_XP_PER_MINUTE_MIN,
  VOICE_XP_PER_MINUTE_MAX,
} from "@/stores/leveling-store";

describe("leveling config voice XP contract", () => {
  it("defaults voice XP to the disabled (0) state and drops the legacy flag", () => {
    expect(DEFAULT_LEVELING_CONFIG.voice_xp_per_minute).toBe(0);
    expect(
      (DEFAULT_LEVELING_CONFIG as Record<string, unknown>).voice_xp_enabled
    ).toBeUndefined();
  });

  it("treats 0 as the floor so voice XP can be disabled", () => {
    expect(VOICE_XP_PER_MINUTE_MIN).toBe(0);
    expect(VOICE_XP_PER_MINUTE_MAX).toBe(100);
    expect(DEFAULT_LEVELING_CONFIG.voice_xp_per_minute).toBeGreaterThanOrEqual(
      VOICE_XP_PER_MINUTE_MIN
    );
    expect(DEFAULT_LEVELING_CONFIG.voice_xp_per_minute).toBeLessThanOrEqual(
      VOICE_XP_PER_MINUTE_MAX
    );
  });
});
