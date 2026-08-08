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
  cilLink,
  cilSend,
  cilPlus,
  cilHistory,
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
} from "@coreui/icons";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { useUiStore } from "@/stores/ui-store";

type SidebarProps = {
  lang?: string;
  dict?: unknown;
};

type SidebarItem = {
  label: string;
  href: string;
  icon: string[];
};

type SidebarGroup = {
  title: string;
  items: SidebarItem[];
};

const GROUPS: SidebarGroup[] = [
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
        label: "Support Tickets",
        href: "/community/tickets",
        icon: cilEnvelopeClosed,
      },
      { label: "Levels & Activity", href: "/community/leveling", icon: cilStar },
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
        label: "Embed Messages",
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
    title: "SECURITY",
    items: [
      { label: "Audit Logs", href: "/security/logs", icon: cilShieldAlt },
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
        label: "Welcome & Leave Messages",
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

export function getSidebarNavItems(lang: string) {
  return GROUPS.flatMap((group) =>
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
          <span className="fw-semibold fs-5">Norgoth</span>
          <span className="d-block small text-body-secondary text-uppercase">
            Community Command Center
          </span>
        </CSidebarBrand>
      </CSidebarHeader>

      <CSidebarNav ref={navRef} className="norgoth-sidebar-scroll">
        {GROUPS.map((group) => (
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
                    {item.label}
                  </CNavLink>
                </CNavItem>
              );
            })}
          </div>
        ))}
      </CSidebarNav>

      <CSidebarFooter className="border-top">
        <div className="d-flex align-items-center gap-3 px-2 py-1">
          <div
            className="d-flex align-items-center justify-content-center rounded-circle border fw-semibold"
            style={{ width: 40, height: 40 }}
          >
            N
          </div>
          <div className="min-w-0">
            <div className="text-truncate small fw-medium">Workspace</div>
            <div
              className="text-truncate text-body-secondary"
              style={{ fontSize: 12 }}
            >
              Discord community tools
            </div>
          </div>
        </div>
      </CSidebarFooter>
    </CSidebar>
  );
}

