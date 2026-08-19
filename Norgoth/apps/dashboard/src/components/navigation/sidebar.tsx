"use client";

import {
  CSidebar,
  CSidebarBrand,
  CSidebarHeader,
  CSidebarNav,
  CSidebarFooter,
  CNavItem,
  CNavLink,
  CNavTitle,
} from "@coreui/react";
import { CIcon } from "@coreui/icons-react";
import {
  cilSpeedometer,
  cilChartLine,
  cilPeople,
  cilEnvelopeClosed,
  cilStar,
  cilBarChart,
  cilLink,
  cilSend,
  cilPlus,
  cilHistory,
  cilNotes,
  cilShieldAlt,
  cilBan,
  cilUserFollow,
  cilCommentBubble,
  cilList,
  cilTags,
  cilBell,
  cilImage,
  cilBug,
  cilTask,
  cilRss,
} from "@coreui/icons";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useMemo, useRef } from "react";
import { useUiStore } from "@/stores/ui-store";
import { useGuildStore } from "@/stores/guild-store";
import { GuildIcon } from "@/components/ui/guild-icon";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";
import type { Dictionary } from "@/app/[lang]/dictionaries";

type SidebarProps = {
  lang?: string;
  dict?: Dictionary | unknown;
};

export type SidebarItem = {
  label: string;
  href: string;
  icon: string[];
};

export type SidebarGroup = {
  title: string;
  items: SidebarItem[];
};

type SidebarLabelKey = keyof typeof en.sidebar;

type SidebarItemDef = {
  labelKey: SidebarLabelKey;
  href: string;
  icon: string[];
};

type SidebarGroupDef = {
  titleKey: SidebarLabelKey;
  items: SidebarItemDef[];
};

const SIDEBAR_DEFS: SidebarGroupDef[] = [
  {
    titleKey: "groupHome",
    items: [
      { labelKey: "dashboard", href: "/dashboard", icon: cilSpeedometer },
      { labelKey: "analytics", href: "/analytics", icon: cilChartLine },
    ],
  },
  {
    titleKey: "groupCommunity",
    items: [
      {
        labelKey: "onboarding",
        href: "/community/onboarding",
        icon: cilPeople,
      },
      {
        labelKey: "manualVerification",
        href: "/community/manual-verification",
        icon: cilTask,
      },
      {
        labelKey: "supportTickets",
        href: "/community/tickets",
        icon: cilEnvelopeClosed,
      },
      {
        labelKey: "levelsActivity",
        href: "/community/leveling",
        icon: cilStar,
      },
      {
        labelKey: "feedChannels",
        href: "/community/feed-channels",
        icon: cilRss,
      },
      {
        labelKey: "leaderboard",
        href: "/community/leaderboard",
        icon: cilBarChart,
      },
      {
        labelKey: "inviteTracking",
        href: "/community/invites",
        icon: cilLink,
      },
    ],
  },
  {
    titleKey: "groupAutomation",
    items: [
      {
        labelKey: "welcomeGoodbyeInvite",
        href: "/automation/welcome-goodbye-invite",
        icon: cilCommentBubble,
      },
      {
        labelKey: "autoResponses",
        href: "/automation/auto-responses",
        icon: cilList,
      },
      { labelKey: "autoRole", href: "/automation/auto-role", icon: cilUserFollow },
      {
        labelKey: "selfAssignableRoles",
        href: "/automation/role-menus",
        icon: cilTags,
      },
      {
        labelKey: "rssFeeds",
        href: "/messages/rss-feeds",
        icon: cilNotes,
      },
      {
        labelKey: "richLinkEmbeds",
        href: "/automation/rich-link-embeds",
        icon: cilLink,
      },
    ],
  },
  {
    titleKey: "groupSecurity",
    items: [
      {
        labelKey: "autoModeration",
        href: "/security/auto-moderation",
        icon: cilBan,
      },
      {
        labelKey: "raidProtection",
        href: "/security/raid-protection",
        icon: cilShieldAlt,
      },
      {
        labelKey: "honeypot",
        href: "/security/honeypot",
        icon: cilBug,
      },
    ],
  },
  {
    titleKey: "groupMessages",
    items: [
      { labelKey: "campaigns", href: "/campaigns", icon: cilSend },
      { labelKey: "createCampaign", href: "/campaigns/new", icon: cilPlus },
      {
        labelKey: "campaignHistory",
        href: "/campaigns/history",
        icon: cilHistory,
      },
      {
        labelKey: "embedLibrary",
        href: "/messages/embed-messages",
        icon: cilImage,
      },
      {
        labelKey: "contentNotifications",
        href: "/messages/content-notifications",
        icon: cilBell,
      },
    ],
  },
  {
    titleKey: "groupAudit",
    items: [
      { labelKey: "auditLogs", href: "/audit/logs", icon: cilNotes },
      {
        labelKey: "discordLogs",
        href: "/audit/discord-logs",
        icon: cilHistory,
      },
    ],
  },
];

function sidebarDict(lang: string) {
  return (lang === "tr" ? tr : en).sidebar;
}

export function getSidebarGroups(lang: string): SidebarGroup[] {
  const labels = sidebarDict(lang);
  return SIDEBAR_DEFS.map((group) => ({
    title: labels[group.titleKey],
    items: group.items.map((item) => ({
      label: labels[item.labelKey],
      href: item.href,
      icon: item.icon,
    })),
  }));
}

/** English snapshot for callers that still import a static constant. */
export const SIDEBAR_GROUPS: SidebarGroup[] = getSidebarGroups("en");

export function getSidebarNavItems(lang: string) {
  return getSidebarGroups(lang).flatMap((group) =>
    group.items.map((item) => ({
      ...item,
      href: `/${lang}${item.href}`,
      group: group.title,
    })),
  );
}

export default function Sidebar({ lang: propLang, dict }: SidebarProps) {
  const params = useParams();
  const pathname = usePathname();
  const navRef = useRef<HTMLUListElement | null>(null);
  const navScrollTop = useUiStore((s) => s.navScrollTop);
  const setNavScrollTop = useUiStore((s) => s.setNavScrollTop);
  const hydrateNavScroll = useUiStore((s) => s.hydrateNavScroll);

  const lang = propLang || String(params?.lang || "en");
  const labels =
    dict && typeof dict === "object" && "sidebar" in dict
      ? (dict as Dictionary).sidebar
      : sidebarDict(lang);

  const groups = useMemo(() => {
    return SIDEBAR_DEFS.map((group) => ({
      titleKey: group.titleKey,
      title: labels[group.titleKey],
      items: group.items.map((item) => ({
        label: labels[item.labelKey],
        href: item.href,
        icon: item.icon,
      })),
    }));
  }, [labels]);

  useEffect(() => {
    hydrateNavScroll();
  }, [hydrateNavScroll]);

  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;
    nav.scrollTop = navScrollTop;
  }, [pathname, navScrollTop]);

  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;

    function onScroll() {
      if (!navRef.current) return;
      setNavScrollTop(navRef.current.scrollTop);
    }

    nav.addEventListener("scroll", onScroll, { passive: true });
    return () => nav.removeEventListener("scroll", onScroll);
  }, [setNavScrollTop]);

  return (
    <CSidebar className="norgoth-sidebar" colorScheme="dark" visible>
      <CSidebarHeader>
        <CSidebarBrand as={Link} href={`/${lang}`} scroll={false}>
          <span className="fw-semibold fs-5">NorBot</span>
          <span className="d-block small text-body-secondary text-uppercase">
            {labels.brandSubtitle}
          </span>
        </CSidebarBrand>
      </CSidebarHeader>

      <CSidebarNav ref={navRef} className="norgoth-sidebar-scroll norgoth-scrollbar">
        {groups.map((group) => (
          <div key={group.titleKey}>
            <CNavTitle>{group.title}</CNavTitle>
            {group.items.map((item) => {
              const href = `/${lang}${item.href}`;
              const active =
                item.href === ""
                  ? pathname === `/${lang}`
                  : pathname === href || pathname.startsWith(`${href}/`);

              return (
                <CNavItem key={`${group.titleKey}-${item.href}`}>
                  <CNavLink as={Link} href={href} active={active} scroll={false}>
                    <CIcon icon={item.icon} className="nav-icon me-2" />
                    {item.label}
                  </CNavLink>
                </CNavItem>
              );
            })}
          </div>
        ))}
      </CSidebarNav>

      <CSidebarFooter className="border-top p-0">
        <SidebarGuildFooter lang={lang} labels={labels} />
      </CSidebarFooter>
    </CSidebar>
  );
}

function SidebarGuildFooter({
  lang,
  labels,
}: {
  lang: string;
  labels: typeof en.sidebar;
}) {
  const selectedGuild = useGuildStore((s) => s.selectedGuild);
  const name = selectedGuild?.name ?? labels.noServerSelected;
  const iconUrl = selectedGuild?.icon_url ?? null;

  return (
    <Link
      href={`/${lang}/servers`}
      scroll={false}
      className="norgoth-sidebar-guild d-flex align-items-center gap-3 px-3 py-2 text-decoration-none text-reset w-100"
      aria-label={`${labels.serverSelection}: ${name}`}
    >
      <GuildIcon url={iconUrl} name={name} size={40} />
      <div className="flex-grow-1 min-w-0">
        <div className="text-truncate small fw-medium" title={name}>
          {name}
        </div>
        <div
          className="text-truncate text-body-secondary"
          style={{ fontSize: 12 }}
        >
          {labels.serverSelection}
        </div>
      </div>
    </Link>
  );
}
