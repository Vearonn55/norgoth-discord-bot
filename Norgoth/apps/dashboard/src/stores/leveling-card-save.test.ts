import { describe, expect, it } from "vitest";
import {
  DEFAULT_LEVELING_CONFIG,
  levelingCardDirty,
  pickLevelingCard,
} from "./leveling-store";

describe("leveling card merge", () => {
  it("picks only XP configuration fields", () => {
    const picked = pickLevelingCard(
      { ...DEFAULT_LEVELING_CONFIG, xp_per_message: 42 },
      "xp"
    );
    expect(picked).toEqual({
      xp_per_message: 42,
      voice_xp_per_minute: 0,
      xp_multiplier: 1,
      level_threshold_scale: 1,
    });
  });

  it("does not treat an unrelated dirty card as dirty for XP", () => {
    const server = DEFAULT_LEVELING_CONFIG;
    const draft = {
      ...server,
      reward_roles: [{ level: 5, role_id: "1" }],
    };
    expect(levelingCardDirty(draft, server, "xp")).toBe(false);
    expect(levelingCardDirty(draft, server, "rewards")).toBe(true);
  });
});
