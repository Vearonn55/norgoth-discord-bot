/**
 * Product category accents (navigation / section identity).
 * Keep separate from status colors (success/danger/warning/info).
 */

export type NorgothCategory =
  | "dashboard"
  | "community"
  | "messages"
  | "campaigns"
  | "moderation"
  | "security"
  | "support"
  | "analytics"
  | "operations"
  | "logging"
  | "roles"
  | "invitations"
  | "leveling";

export type CategoryTokens = {
  id: NorgothCategory;
  label: string;
  /** CSS custom property name without var() */
  cssVar: string;
  /** Fallback hex for inline styles */
  color: string;
};

export const CATEGORY_TOKENS: Record<NorgothCategory, CategoryTokens> = {
  dashboard: {
    id: "dashboard",
    label: "Dashboard",
    cssVar: "--norgoth-cat-dashboard",
    color: "#6ea8fe",
  },
  community: {
    id: "community",
    label: "Community",
    cssVar: "--norgoth-cat-community",
    color: "#3dd68c",
  },
  messages: {
    id: "messages",
    label: "Messages",
    cssVar: "--norgoth-cat-messages",
    color: "#5ec8ff",
  },
  campaigns: {
    id: "campaigns",
    label: "Campaigns",
    cssVar: "--norgoth-cat-campaigns",
    color: "#b794f6",
  },
  moderation: {
    id: "moderation",
    label: "Moderation",
    cssVar: "--norgoth-cat-moderation",
    color: "#ff6b7a",
  },
  security: {
    id: "security",
    label: "Security",
    cssVar: "--norgoth-cat-security",
    color: "#ff8f6b",
  },
  support: {
    id: "support",
    label: "Support",
    cssVar: "--norgoth-cat-support",
    color: "#5eead4",
  },
  analytics: {
    id: "analytics",
    label: "Analytics",
    cssVar: "--norgoth-cat-analytics",
    color: "#f0abfc",
  },
  operations: {
    id: "operations",
    label: "Operations",
    cssVar: "--norgoth-cat-operations",
    color: "#94a3b8",
  },
  logging: {
    id: "logging",
    label: "Logging",
    cssVar: "--norgoth-cat-logging",
    color: "#fbbf24",
  },
  roles: {
    id: "roles",
    label: "Roles",
    cssVar: "--norgoth-cat-roles",
    color: "#f472b6",
  },
  invitations: {
    id: "invitations",
    label: "Invitations",
    cssVar: "--norgoth-cat-invitations",
    color: "#34d399",
  },
  leveling: {
    id: "leveling",
    label: "Leveling",
    cssVar: "--norgoth-cat-leveling",
    color: "#facc15",
  },
};

export function categoryAccent(category: NorgothCategory): string {
  return `var(${CATEGORY_TOKENS[category].cssVar}, ${CATEGORY_TOKENS[category].color})`;
}
