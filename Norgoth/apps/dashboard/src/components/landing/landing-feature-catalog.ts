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
  icon: string[];
};

export const LANDING_FEATURE_CATALOG: LandingFeatureDef[] = [
  { id: "verification", category: "community", icon: cilPeople },
  { id: "manualReview", category: "community", icon: cilTask },
  { id: "tickets", category: "support", icon: cilEnvelopeClosed },
  { id: "leveling", category: "leveling", icon: cilStar },
  { id: "leaderboard", category: "leveling", icon: cilBarChart },
  { id: "feedChannels", category: "community", icon: cilRss },
  { id: "invites", category: "invitations", icon: cilLink },
  { id: "welcome", category: "community", icon: cilCommentBubble },
  { id: "autoresponder", category: "community", icon: cilList },
  { id: "autorole", category: "roles", icon: cilUserFollow },
  { id: "roleMenus", category: "roles", icon: cilTags },
  { id: "rss", category: "messages", icon: cilNotes },
  { id: "linkEmbeds", category: "messages", icon: cilLink },
  { id: "automod", category: "moderation", icon: cilBan },
  { id: "raid", category: "security", icon: cilShieldAlt },
  { id: "honeypot", category: "security", icon: cilBug },
  { id: "campaigns", category: "campaigns", icon: cilSend },
  { id: "embeds", category: "messages", icon: cilImage },
  { id: "notifications", category: "messages", icon: cilBell },
  { id: "discordLogs", category: "logging", icon: cilHistory },
  { id: "auditLogs", category: "logging", icon: cilNotes },
  { id: "analytics", category: "analytics", icon: cilChartLine },
];

export function landingFeatureDef(id: LandingFeatureId): LandingFeatureDef {
  const match = LANDING_FEATURE_CATALOG.find((item) => item.id === id);
  if (!match) {
    throw new Error(`Unknown landing feature: ${id}`);
  }
  return match;
}
