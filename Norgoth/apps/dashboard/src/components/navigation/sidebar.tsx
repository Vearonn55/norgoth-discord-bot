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
  cilHeart,
  cilCog,
  cilImage,
  cilBug,
  cilTask,
  cilRss,
} from "@coreui/icons";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { useUiStore } from "@/stores/ui-store";
import { useGuildStore } from "@/stores/guild-store";
import { GuildIcon } from "@/components/ui/guild-icon";

type SidebarProps = {
  lang?: string;
  dict?: unknown;
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

export const SIDEBAR_GROUPS: SidebarGroup[] = [
  {
    title: "HOME",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: cilSpeedometer },
      { label: "Analytics", href: "/analytics", icon: cilChartLine },
    ],
  },
  {
    title: "COMMUNITY",
    items: [
      {
        label: "Member Verification",
        href: "/community/onboarding",
        icon: cilPeople,
      },
      {
        label: "Manual Verification",
        href: "/community/manual-verification",
        icon: cilTask,
      },
      {
        label: "Support Tickets",
        href: "/community/tickets",
        icon: cilEnvelopeClosed,
      },
      { label: "Levels & Activity", href: "/community/leveling", icon: cilStar },
      {
        label: "Top Trending",
        href: "/community/feed-channels",
        icon: cilRss,
      },
      {
        label: "Leaderboards",
        href: "/community/leaderboard",
        icon: cilBarChart,
      },
      { label: "Invite Tracking", href: "/community/invites", icon: cilLink },
    ],
  },
  {
    title: "MESSAGES",
    items: [
      { label: "Campaigns", href: "/campaigns", icon: cilSend },
      { label: "Create Campaign", href: "/campaigns/new", icon: cilPlus },
      { label: "Campaign History", href: "/campaigns/history", icon: cilHistory },
      {
        label: "Embed Library",
        href: "/messages/embed-messages",
        icon: cilImage,
      },
      {
        label: "Content Notifications",
        href: "/messages/content-notifications",
        icon: cilBell,
      },
    ],
  },
  {
    title: "AUDIT",
    items: [
      { label: "Audit Logs", href: "/audit/logs", icon: cilNotes },
      {
        label: "Discord Logs",
        href: "/audit/discord-logs",
        icon: cilHistory,
      },
    ],
  },
  {
    title: "SECURITY",
    items: [
      {
        label: "Auto-Moderation",
        href: "/security/auto-moderation",
        icon: cilBan,
      },
      {
        label: "Raid Protection",
        href: "/security/raid-protection",
        icon: cilShieldAlt,
      },
      {
        label: "Honeypot",
        href: "/security/honeypot",
        icon: cilBug,
      },
    ],
  },
  {
    title: "AUTOMATION",
    items: [
      { label: "Auto Role", href: "/automation/auto-role", icon: cilUserFollow },
      {
        label: "Welcome & Leave",
        href: "/automation/welcome-goodbye-invite",
        icon: cilCommentBubble,
      },
      {
        label: "Auto-Responses",
        href: "/automation/auto-responses",
        icon: cilList,
      },
      {
        label: "Self-Assignable Roles",
        href: "/automation/role-menus",
        icon: cilTags,
      },
    ],
  },
  {
    title: "SYSTEM",
    items: [
      {
        label: "Worker Health",
        href: "/observability/worker-health",
        icon: cilHeart,
      },
      { label: "Settings", href: "/settings", icon: cilCog },
    ],
  },
];

function localizedSidebarLabel(lang: string, item: SidebarItem): string {
  if (item.href === "/audit/logs") {
    return lang === "tr" ? "Denetim Kayıtları" : "Audit Logs";
  }
  if (item.href === "/audit/discord-logs") {
    return lang === "tr" ? "Discord Kayıtları" : "Discord Logs";
  }
  return item.label;
}
export function getSidebarNavItems(lang: string) {
  return SIDEBAR_GROUPS.flatMap((group) =>
    group.items.map((item) => ({
      ...item,
      href: `/${lang}${item.href}`,
      group: group.title,
    }))
  );
}

export default function Sidebar({ lang: propLang }: SidebarProps) {
  const params = useParams();
  const pathname = usePathname();
  const navRef = useRef<HTMLUListElement | null>(null);
  const navScrollTop = useUiStore((s) => s.navScrollTop);
  const setNavScrollTop = useUiStore((s) => s.setNavScrollTop);
  const hydrateNavScroll = useUiStore((s) => s.hydrateNavScroll);

  const lang = propLang || String(params?.lang || "en");

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
            Community Command Center
          </span>
        </CSidebarBrand>
      </CSidebarHeader>

      <CSidebarNav ref={navRef} className="norgoth-sidebar-scroll">
        {SIDEBAR_GROUPS.map((group) => (
          <div key={group.title}>
            <CNavTitle>{group.title}</CNavTitle>
            {group.items.map((item) => {
              const href = `/${lang}${item.href}`;
              const active =
                item.href === ""
                  ? pathname === `/${lang}`
                  : pathname === href || pathname.startsWith(`${href}/`);

              return (
                <CNavItem key={`${group.title}-${item.href}`}>
                  <CNavLink as={Link} href={href} active={active} scroll={false}>
                    <CIcon icon={item.icon} className="nav-icon me-2" />
                    {localizedSidebarLabel(lang, item)}
                  </CNavLink>
                </CNavItem>
              );
            })}
          </div>
        ))}
      </CSidebarNav>

      <CSidebarFooter className="border-top p-0">
        <SidebarGuildFooter lang={lang} />
      </CSidebarFooter>
    </CSidebar>
  );
}

function SidebarGuildFooter({ lang }: { lang: string }) {
  const selectedGuild = useGuildStore((s) => s.selectedGuild);
  const name = selectedGuild?.name ?? "No server selected";
  const iconUrl = selectedGuild?.icon_url ?? null;

  return (
    <Link
      href={`/${lang}/servers`}
      scroll={false}
      className="norgoth-sidebar-guild d-flex align-items-center gap-3 px-3 py-2 text-decoration-none text-reset"
      aria-label={`Change selected server: ${name}`}
    >
      <GuildIcon url={iconUrl} name={name} size={40} />
      <div className="min-w-0">
        <div className="text-truncate small fw-medium" title={name}>
          {name}
        </div>
        <div
          className="text-truncate text-body-secondary"
          style={{ fontSize: 12 }}
        >
          Server Selection
        </div>
      </div>
    </Link>
  );
}


