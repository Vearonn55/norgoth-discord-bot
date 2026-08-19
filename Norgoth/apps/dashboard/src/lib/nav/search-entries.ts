import {
  getSidebarGroups,
  type SidebarItem,
} from "@/components/navigation/sidebar";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";

export type SearchEntryKind = "page" | "subfeature";

export type SearchEntry = {
  id: string;
  label: string;
  keywords: string[];
  href: string;
  group: string;
  parentId?: string;
  parentLabel?: string;
  kind: SearchEntryKind;
  icon?: string[];
};

/** Logging category keys/labels aligned with API EVENT_GROUPS. */
export const LOGGING_CATEGORY_SEARCH: Array<{
  key: string;
  label: string;
  keywords: string[];
}> = [
  { key: "member", label: "Members", keywords: ["member logs", "joins", "bans"] },
  { key: "message", label: "Messages", keywords: ["message logs", "edits", "deletes"] },
  { key: "channel", label: "Channels", keywords: ["channel logs"] },
  { key: "role", label: "Roles", keywords: ["role logs"] },
  { key: "server", label: "Server", keywords: ["guild logs", "server logs"] },
  { key: "voice", label: "Voice", keywords: ["voice logs"] },
  { key: "thread", label: "Threads", keywords: ["thread logs"] },
  { key: "moderation", label: "Moderation", keywords: ["mod logs"] },
  { key: "security", label: "Security", keywords: ["honeypot", "raid", "automod"] },
  { key: "tickets", label: "Tickets", keywords: ["ticket logs"] },
  {
    key: "invites",
    label: "Invites",
    keywords: ["invite logs", "invite logging", "invites"],
  },
];

function pageId(item: SidebarItem): string {
  return item.href.replace(/^\//, "").replace(/\//g, ".") || "home";
}

/**
 * Build the global command-palette index: sidebar pages + curated sub-features.
 */
export function getSearchEntries(lang: string): SearchEntry[] {
  const groups = getSidebarGroups(lang);
  const sidebar = (lang === "tr" ? tr : en).sidebar;
  const pages: SearchEntry[] = groups.flatMap((group) =>
    group.items.map((item) => ({
      id: `page:${pageId(item)}`,
      label: item.label,
      keywords: [],
      href: `/${lang}${item.href}`,
      group: group.title,
      kind: "page" as const,
      icon: item.icon,
    }))
  );

  const pageByHref = new Map(pages.map((p) => [p.href.replace(`/${lang}`, "") || "/", p]));

  function parent(path: string): { id: string; label: string } | undefined {
    const entry = pageByHref.get(path);
    if (!entry) return undefined;
    return { id: entry.id, label: entry.label };
  }

  const leaderboard = parent("/community/leaderboard");
  const feedChannels = parent("/community/feed-channels");
  const discordLogs = parent("/audit/discord-logs");
  const contentNotifications = parent("/messages/content-notifications");
  const rssFeeds = parent("/messages/rss-feeds");
  const tickets = parent("/community/tickets");
  const leveling = parent("/community/leveling");
  const autoRole = parent("/automation/auto-role");
  const welcome = parent("/automation/welcome-goodbye-invite");

  const subfeatures: SearchEntry[] = [
    {
      id: "sub:leaderboard.text",
      label: "Text XP",
      keywords: ["text xp", "text leaderboard", "message xp"],
      href: `/${lang}/community/leaderboard?metric=text`,
      group: sidebar.groupCommunity,
      parentId: leaderboard?.id,
      parentLabel: leaderboard?.label ?? sidebar.leaderboard,
      kind: "subfeature",
    },
    {
      id: "sub:leaderboard.voice",
      label: "Voice XP",
      keywords: ["voice xp", "voice leaderboard"],
      href: `/${lang}/community/leaderboard?metric=voice`,
      group: sidebar.groupCommunity,
      parentId: leaderboard?.id,
      parentLabel: leaderboard?.label ?? sidebar.leaderboard,
      kind: "subfeature",
    },
    {
      id: "sub:leaderboard.net-upvotes",
      label: "Top Upvote",
      keywords: [
        "net upvotes",
        "net upvote",
        "upvote leaderboard",
        "feed channels",
        "top trending",
        "all-time upvotes",
      ],
      href: `/${lang}/community/leaderboard?metric=net_upvotes`,
      group: sidebar.groupCommunity,
      parentId: leaderboard?.id,
      parentLabel: leaderboard?.label ?? sidebar.leaderboard,
      kind: "subfeature",
    },
    {
      id: "sub:feed-channels.daily",
      label: "Daily Feed",
      keywords: ["daily feed", "feed channels", "top trending", "net upvote"],
      href: `/${lang}/community/feed-channels`,
      group: sidebar.groupCommunity,
      parentId: feedChannels?.id,
      parentLabel: feedChannels?.label ?? sidebar.feedChannels,
      kind: "subfeature",
    },
    {
      id: "sub:feed-channels.weekly",
      label: "Weekly Feed",
      keywords: ["weekly feed", "feed channels", "top trending"],
      href: `/${lang}/community/feed-channels`,
      group: sidebar.groupCommunity,
      parentId: feedChannels?.id,
      parentLabel: feedChannels?.label ?? sidebar.feedChannels,
      kind: "subfeature",
    },
    {
      id: "sub:feed-channels.monthly",
      label: "Monthly Feed",
      keywords: ["monthly feed", "feed channels", "top trending"],
      href: `/${lang}/community/feed-channels`,
      group: sidebar.groupCommunity,
      parentId: feedChannels?.id,
      parentLabel: feedChannels?.label ?? sidebar.feedChannels,
      kind: "subfeature",
    },
    {
      id: "sub:feed-channels.all-time",
      label: "All-Time Feed",
      keywords: ["all-time feed", "all time feed", "feed channels", "top trending"],
      href: `/${lang}/community/feed-channels`,
      group: sidebar.groupCommunity,
      parentId: feedChannels?.id,
      parentLabel: feedChannels?.label ?? sidebar.feedChannels,
      kind: "subfeature",
    },
    ...LOGGING_CATEGORY_SEARCH.map((cat) => ({
      id: `sub:discord-logs.${cat.key}`,
      label: cat.label,
      keywords: [...cat.keywords, "discord logs", "logging", cat.key],
      href: `/${lang}/audit/discord-logs?channel=${cat.key}`,
      group: sidebar.groupAudit,
      parentId: discordLogs?.id,
      parentLabel: discordLogs?.label ?? sidebar.discordLogs,
      kind: "subfeature" as const,
    })),
    {
      id: "sub:content-notifications.templates",
      label: "Templates",
      keywords: ["notification templates"],
      href: `/${lang}/messages/content-notifications/templates`,
      group: sidebar.groupMessages,
      parentId: contentNotifications?.id,
      parentLabel: contentNotifications?.label ?? sidebar.contentNotifications,
      kind: "subfeature",
    },
    {
      id: "sub:content-notifications.sender-styles",
      label: "Sender Styles",
      keywords: ["sender styles", "webhooks"],
      href: `/${lang}/messages/content-notifications/sender-styles`,
      group: sidebar.groupMessages,
      parentId: contentNotifications?.id,
      parentLabel: contentNotifications?.label ?? sidebar.contentNotifications,
      kind: "subfeature",
    },
    {
      id: "sub:content-notifications.history",
      label: "History",
      keywords: ["notification history"],
      href: `/${lang}/messages/content-notifications/history`,
      group: sidebar.groupMessages,
      parentId: contentNotifications?.id,
      parentLabel: contentNotifications?.label ?? sidebar.contentNotifications,
      kind: "subfeature",
    },
    {
      id: "sub:content-notifications.analytics",
      label: "Analytics",
      keywords: ["notification analytics"],
      href: `/${lang}/messages/content-notifications/analytics`,
      group: sidebar.groupMessages,
      parentId: contentNotifications?.id,
      parentLabel: contentNotifications?.label ?? sidebar.contentNotifications,
      kind: "subfeature",
    },
    {
      id: "sub:rss-feeds.add",
      label: "Add RSS feed",
      keywords: ["atom", "rss", "feed url", "syndication"],
      href: `/${lang}/messages/rss-feeds`,
      group: sidebar.groupMessages,
      parentId: rssFeeds?.id,
      parentLabel: rssFeeds?.label ?? sidebar.rssFeeds,
      kind: "subfeature",
    },
    {
      id: "sub:tickets.panels",
      label: "Ticket Panels",
      keywords: ["ticket panels", "support panels", "panels"],
      href: `/${lang}/community/tickets`,
      group: sidebar.groupCommunity,
      parentId: tickets?.id,
      parentLabel: tickets?.label ?? sidebar.supportTickets,
      kind: "subfeature",
    },
    {
      id: "sub:leveling.voice-xp",
      label: "Voice XP Settings",
      keywords: ["voice xp", "leveling voice", "activity voice"],
      href: `/${lang}/community/leveling`,
      group: sidebar.groupCommunity,
      parentId: leveling?.id,
      parentLabel: leveling?.label ?? sidebar.levelsActivity,
      kind: "subfeature",
    },
    {
      id: "sub:leveling.text-xp",
      label: "Text XP Settings",
      keywords: ["text xp", "leveling text", "message xp"],
      href: `/${lang}/community/leveling`,
      group: sidebar.groupCommunity,
      parentId: leveling?.id,
      parentLabel: leveling?.label ?? sidebar.levelsActivity,
      kind: "subfeature",
    },
    {
      id: "sub:autorole",
      label: "Auto Role",
      keywords: ["autorole", "join role", "auto roles"],
      href: `/${lang}/automation/auto-role`,
      group: sidebar.groupAutomation,
      parentId: autoRole?.id,
      parentLabel: autoRole?.label ?? sidebar.autoRole,
      kind: "subfeature",
    },
    {
      id: "sub:welcome",
      label: "Welcome & Leave",
      keywords: ["welcome", "goodbye", "leave message"],
      href: `/${lang}/automation/welcome-goodbye-invite`,
      group: sidebar.groupAutomation,
      parentId: welcome?.id,
      parentLabel: welcome?.label ?? sidebar.welcomeGoodbyeInvite,
      kind: "subfeature",
    },
  ];

  // Enrich page entries with useful aliases without duplicating rows.
  for (const page of pages) {
    if (page.href.endsWith("/community/leaderboard")) {
      page.keywords.push("leaderboard", "xp ranks", "ranking");
    }
    if (page.href.endsWith("/audit/discord-logs")) {
      page.keywords.push("logging", "server logs", "event logs");
    }
    if (page.href.endsWith("/automation/auto-role")) {
      page.keywords.push("autorole", "join role");
    }
    if (page.href.endsWith("/automation/rich-link-embeds")) {
      page.keywords.push(
        "link embeds",
        "rich link embeds",
        "bağlantı önizlemeleri",
        "fxtwitter",
        "tnktok",
        "tiktok",
        "embed fixer",
        "instagram",
        "pixiv",
        "youtube shorts",
      );
    }
    if (page.href.endsWith("/messages/content-notifications")) {
      page.keywords.push(
        "content notifications",
        "içerik bildirimleri",
        "kick",
        "twitch",
        "youtube",
        "livestream",
      );
    }
  }

  return [...pages, ...subfeatures];
}

function scoreEntry(entry: SearchEntry, q: string): number {
  const label = entry.label.toLowerCase();
  const parent = (entry.parentLabel ?? "").toLowerCase();
  const haystacks = [
    label,
    parent,
    entry.group.toLowerCase(),
    ...entry.keywords.map((k) => k.toLowerCase()),
    entry.href.toLowerCase(),
  ];

  if (label === q) return 100;
  if (parent && `${parent} ${label}` === q) return 95;
  if (label.startsWith(q)) return 80;
  if (entry.keywords.some((k) => k.toLowerCase() === q)) return 75;
  if (entry.keywords.some((k) => k.toLowerCase().startsWith(q))) return 65;
  if (haystacks.some((h) => h.includes(q))) {
    if (label.includes(q)) return 50;
    if (parent.includes(q)) return 40;
    return 30;
  }
  return 0;
}

/** Filter + rank search entries for the command palette. */
export function filterSearchEntries(
  entries: SearchEntry[],
  query: string
): SearchEntry[] {
  const q = query.trim().toLowerCase();
  if (!q) {
    // Default view: pages first, then a light sample of subfeatures is noisy —
    // show pages only when idle.
    return entries.filter((e) => e.kind === "page");
  }

  return entries
    .map((entry) => ({ entry, score: scoreEntry(entry, q) }))
    .filter((row) => row.score > 0)
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      if (a.entry.kind !== b.entry.kind) {
        return a.entry.kind === "page" ? -1 : 1;
      }
      return a.entry.label.localeCompare(b.entry.label);
    })
    .map((row) => row.entry);
}

export function formatSearchEntryLabel(entry: SearchEntry): string {
  if (entry.kind === "subfeature" && entry.parentLabel) {
    return `${entry.parentLabel} › ${entry.label}`;
  }
  return entry.label;
}
