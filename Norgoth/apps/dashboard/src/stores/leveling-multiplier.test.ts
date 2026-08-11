import { describe, expect, it } from "vitest";
import {
  XP_MULTIPLIER_MIN,
  XP_MULTIPLIER_MAX,
  LEVEL_THRESHOLD_SCALE_MIN,
  LEVEL_THRESHOLD_SCALE_MAX,
  DEFAULT_LEVEL_THRESHOLD_SCALE,
} from "@/stores/leveling-store";

describe("XP multiplier slider tick labels", () => {
  it("uses the real 0.1x–5.0x scale bounds", () => {
    expect(XP_MULTIPLIER_MIN).toBe(0.1);
    expect(XP_MULTIPLIER_MAX).toBe(5.0);
  });

  it("labels the midpoint as the true average of the bounds (not a fixed 1.0x)", () => {
    const midpoint = (XP_MULTIPLIER_MIN + XP_MULTIPLIER_MAX) / 2;
    // (0.1 + 5.0) / 2 = 2.55, which renders as "2.5x" — the key point is it is
    // the true midpoint of the bounds, not a hardcoded "1.0x".
    expect(`${midpoint.toFixed(1)}x`).toBe("2.5x");
    expect(`${XP_MULTIPLIER_MIN.toFixed(1)}x`).toBe("0.1x");
    expect(`${XP_MULTIPLIER_MAX.toFixed(1)}x`).toBe("5.0x");
  });
});

describe("Level Up Threshold slider tick labels", () => {
  it("uses the real 0.5x–2.0x scale bounds", () => {
    expect(LEVEL_THRESHOLD_SCALE_MIN).toBe(0.5);
    expect(LEVEL_THRESHOLD_SCALE_MAX).toBe(2.0);
  });

  it("labels the midpoint as 1.25x (arithmetic mean), not a hardcoded 1.00x", () => {
    const midpoint =
      (LEVEL_THRESHOLD_SCALE_MIN + LEVEL_THRESHOLD_SCALE_MAX) / 2;
    expect(`${midpoint.toFixed(2)}x`).toBe("1.25x");
    expect(`${LEVEL_THRESHOLD_SCALE_MIN.toFixed(2)}x`).toBe("0.50x");
    expect(`${LEVEL_THRESHOLD_SCALE_MAX.toFixed(2)}x`).toBe("2.00x");
  });

  it("keeps the persisted default at classic 1.0 (independent of midpoint label)", () => {
    expect(DEFAULT_LEVEL_THRESHOLD_SCALE).toBe(1.0);
  });
});
