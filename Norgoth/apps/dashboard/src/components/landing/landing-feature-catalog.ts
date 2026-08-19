import {
  cilBan,
  cilBarChart,
  cilBell,
  cilBug,
  cilChartLine,
  cilCommentBubble,
  cilEnvelopeClosed,
  cilHistory,
  cilImage,
  cilLink,
  cilList,
  cilNotes,
  cilPeople,
  cilRss,
  cilSend,
  cilShieldAlt,
  cilStar,
  cilTags,
  cilTask,
  cilUserFollow,
} from "@coreui/icons";
import type { NorgothCategory } from "@/lib/design/category";

export const LANDING_FEATURE_IDS = [
  "verification",
  "manualReview",
  "tickets",
  "leveling",
  "leaderboard",
  "feedChannels",
  "invites",
  "welcome",
  "autoresponder",
  "autorole",
  "roleMenus",
  "rss",
  "linkEmbeds",
  "automod",
  "raid",
  "honeypot",
  "campaigns",
  "embeds",
  "notifications",
  "discordLogs",
  "auditLogs",
  "analytics",
] as const;

export type LandingFeatureId = (typeof LANDING_FEATURE_IDS)[number];

export const LANDING_NAV_GROUPS = [
  "groupHome",
  "groupCommunity",
  "groupAutomation",
  "groupSecurity",
  "groupMessages",
  "groupAudit",
] as const;

export type LandingNavGroup = (typeof LANDING_NAV_GROUPS)[number];

export const LANDING_SHOWCASE_IDS: LandingFeatureId[] = [
  "verification",
  "automod",
  "campaigns",
  "tickets",
  "leveling",
  "notifications",
];

export type LandingFeatureDef = {
  id: LandingFeatureId;
  category: NorgothCategory;
  navGroup: LandingNavGroup;
  icon: string[];
};

export const LANDING_FEATURE_CATALOG: LandingFeatureDef[] = [
  { id: "verification", category: "community", navGroup: "groupCommunity", icon: cilPeople },
  { id: "manualReview", category: "community", navGroup: "groupCommunity", icon: cilTask },
  { id: "tickets", category: "support", navGroup: "groupCommunity", icon: cilEnvelopeClosed },
  { id: "leveling", category: "leveling", navGroup: "groupCommunity", icon: cilStar },
  { id: "leaderboard", category: "leveling", navGroup: "groupCommunity", icon: cilBarChart },
  { id: "feedChannels", category: "community", navGroup: "groupCommunity", icon: cilRss },
  { id: "invites", category: "invitations", navGroup: "groupCommunity", icon: cilLink },
  { id: "welcome", category: "community", navGroup: "groupAutomation", icon: cilCommentBubble },
  { id: "autoresponder", category: "community", navGroup: "groupAutomation", icon: cilList },
  { id: "autorole", category: "roles", navGroup: "groupAutomation", icon: cilUserFollow },
  { id: "roleMenus", category: "roles", navGroup: "groupAutomation", icon: cilTags },
  { id: "rss", category: "messages", navGroup: "groupAutomation", icon: cilNotes },
  { id: "linkEmbeds", category: "messages", navGroup: "groupAutomation", icon: cilLink },
  { id: "automod", category: "moderation", navGroup: "groupSecurity", icon: cilBan },
  { id: "raid", category: "security", navGroup: "groupSecurity", icon: cilShieldAlt },
  { id: "honeypot", category: "security", navGroup: "groupSecurity", icon: cilBug },
  { id: "campaigns", category: "campaigns", navGroup: "groupMessages", icon: cilSend },
  { id: "embeds", category: "messages", navGroup: "groupMessages", icon: cilImage },
  { id: "notifications", category: "messages", navGroup: "groupMessages", icon: cilBell },
  { id: "discordLogs", category: "logging", navGroup: "groupAudit", icon: cilHistory },
  { id: "auditLogs", category: "logging", navGroup: "groupAudit", icon: cilNotes },
  { id: "analytics", category: "analytics", navGroup: "groupHome", icon: cilChartLine },
];

export const LANDING_AUTOMATION_IDS: LandingFeatureId[] = LANDING_FEATURE_CATALOG.filter(
  (item) => item.navGroup === "groupAutomation",
).map((item) => item.id);

export function landingFeatureDef(id: LandingFeatureId): LandingFeatureDef {
  const match = LANDING_FEATURE_CATALOG.find((item) => item.id === id);
  if (!match) {
    throw new Error(`Unknown landing feature: ${id}`);
  }
  return match;
}

export function landingNavGroupLabel(
  id: LandingFeatureId,
  sidebar: Record<string, string>,
): string {
  const def = landingFeatureDef(id);
  const label = sidebar[def.navGroup];
  if (!label) {
    throw new Error(`Missing sidebar label for ${def.navGroup}`);
  }
  return label;
}
