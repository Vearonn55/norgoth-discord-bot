import { describe, expect, it } from "vitest";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";
import {
  LANDING_AUTOMATION_IDS,
  LANDING_FEATURE_CATALOG,
  LANDING_FEATURE_IDS,
  LANDING_SHOWCASE_IDS,
  landingFeatureDef,
  landingNavGroupLabel,
} from "@/components/landing/landing-feature-catalog";

const EXPECTED_GROUPS: Record<(typeof LANDING_FEATURE_IDS)[number], string> = {
  verification: "groupCommunity",
  manualReview: "groupCommunity",
  tickets: "groupCommunity",
  leveling: "groupCommunity",
  leaderboard: "groupCommunity",
  feedChannels: "groupCommunity",
  invites: "groupCommunity",
  welcome: "groupAutomation",
  autoresponder: "groupAutomation",
  autorole: "groupAutomation",
  roleMenus: "groupAutomation",
  rss: "groupAutomation",
  linkEmbeds: "groupAutomation",
  automod: "groupSecurity",
  raid: "groupSecurity",
  honeypot: "groupSecurity",
  campaigns: "groupMessages",
  embeds: "groupMessages",
  notifications: "groupMessages",
  discordLogs: "groupAudit",
  auditLogs: "groupAudit",
  analytics: "groupHome",
};

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

  it("maps every feature to a Command Center sidebar group", () => {
    for (const id of LANDING_FEATURE_IDS) {
      const def = landingFeatureDef(id);
      expect(def.navGroup).toBe(EXPECTED_GROUPS[id]);
      expect(landingNavGroupLabel(id, en.sidebar)).toBe(en.sidebar[def.navGroup]);
      expect(landingNavGroupLabel(id, tr.sidebar)).toBe(tr.sidebar[def.navGroup]);
    }
    expect(LANDING_AUTOMATION_IDS.sort()).toEqual(
      [
        "welcome",
        "autoresponder",
        "autorole",
        "roleMenus",
        "rss",
        "linkEmbeds",
      ].sort(),
    );
    for (const id of LANDING_FEATURE_IDS) {
      if (!LANDING_AUTOMATION_IDS.includes(id)) {
        expect(landingNavGroupLabel(id, en.sidebar)).not.toBe(en.sidebar.groupAutomation);
      }
    }
  });

  it("fails when a sidebar group label is missing", () => {
    expect(() => landingNavGroupLabel("verification", {})).toThrow(
      /Missing sidebar label/,
    );
  });
});
