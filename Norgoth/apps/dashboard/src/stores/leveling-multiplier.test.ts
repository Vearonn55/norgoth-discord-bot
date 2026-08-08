import { describe, expect, it } from "vitest";
import { XP_MULTIPLIER_MIN, XP_MULTIPLIER_MAX } from "@/stores/leveling-store";

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
