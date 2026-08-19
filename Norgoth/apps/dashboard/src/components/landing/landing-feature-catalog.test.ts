import { describe, expect, it } from "vitest";
import {
  LANDING_FEATURE_CATALOG,
  LANDING_FEATURE_IDS,
  LANDING_SHOWCASE_IDS,
  landingFeatureDef,
} from "@/components/landing/landing-feature-catalog";

describe("landing feature catalog", () => {
  it("lists only production module ids", () => {
    expect(LANDING_FEATURE_IDS).toHaveLength(22);
    expect(new Set(LANDING_FEATURE_IDS).size).toBe(LANDING_FEATURE_IDS.length);
    expect(LANDING_FEATURE_CATALOG).toHaveLength(LANDING_FEATURE_IDS.length);
    expect(LANDING_SHOWCASE_IDS).toEqual([
      "verification",
      "automod",
      "campaigns",
      "tickets",
      "leveling",
      "notifications",
    ]);
  });

  it("resolves category and icon for each id", () => {
    for (const id of LANDING_FEATURE_IDS) {
      const def = landingFeatureDef(id);
      expect(def.id).toBe(id);
      expect(def.icon.length).toBeGreaterThan(0);
      expect(def.category).toBeTruthy();
    }
  });
});
