import { describe, expect, it } from "vitest";
import { cilNotes } from "@coreui/icons";
import { getSidebarGroups } from "@/components/navigation/sidebar";
import { getSearchEntries } from "@/lib/nav/search-entries";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";

function itemByHref(lang: string, href: string) {
  return getSidebarGroups(lang)
    .flatMap((group) => group.items)
    .find((item) => item.href === href);
}

const RSS_HREF = "/messages/rss-feeds";

const AUTOMATION_HREFS = [
  "/automation/welcome-goodbye-invite",
  "/automation/auto-responses",
  "/automation/auto-role",
  "/automation/role-menus",
  RSS_HREF,
  "/automation/rich-link-embeds",
];

const MESSAGES_HREFS = [
  "/campaigns",
  "/campaigns/new",
  "/campaigns/history",
  "/messages/embed-messages",
  "/messages/content-notifications",
];

const SECURITY_HREFS = [
  "/security/auto-moderation",
  "/security/raid-protection",
  "/security/honeypot",
];

describe("sidebar labels", () => {
  it("keeps English dashboard and embed library labels", () => {
    expect(itemByHref("en", "/dashboard")?.label).toBe("Dashboard");
    expect(itemByHref("en", "/messages/embed-messages")?.label).toBe(
      "Embed Library",
    );
  });

  it("uses corrected Turkish dashboard and embed library labels", () => {
    expect(itemByHref("tr", "/dashboard")?.label).toBe("Genel Bakış");
    expect(itemByHref("tr", "/messages/embed-messages")?.label).toBe(
      "Embed Kitaplığı",
    );
  });
});

describe("sidebar category order", () => {
  it("places Security immediately above Messages in English and Turkish", () => {
    for (const lang of ["en", "tr"] as const) {
      const titles = getSidebarGroups(lang).map((group) => group.title);
      const community = lang === "tr" ? tr.sidebar.groupCommunity : en.sidebar.groupCommunity;
      const automation = lang === "tr" ? tr.sidebar.groupAutomation : en.sidebar.groupAutomation;
      const security = lang === "tr" ? tr.sidebar.groupSecurity : en.sidebar.groupSecurity;
      const messages = lang === "tr" ? tr.sidebar.groupMessages : en.sidebar.groupMessages;
      const communityIdx = titles.indexOf(community);
      const automationIdx = titles.indexOf(automation);
      const securityIdx = titles.indexOf(security);
      const messagesIdx = titles.indexOf(messages);
      expect(communityIdx).toBeGreaterThan(-1);
      expect(automationIdx).toBe(communityIdx + 1);
      expect(securityIdx).toBe(messagesIdx - 1);
      expect(new Set(titles).size).toBe(titles.length);
      expect(titles).toEqual([
        lang === "tr" ? tr.sidebar.groupHome : en.sidebar.groupHome,
        community,
        automation,
        security,
        messages,
        lang === "tr" ? tr.sidebar.groupAudit : en.sidebar.groupAudit,
      ]);
    }
  });

  it("keeps Security child routes and order unchanged", () => {
    for (const lang of ["en", "tr"] as const) {
      const security = getSidebarGroups(lang).find(
        (group) =>
          group.title ===
          (lang === "tr" ? tr.sidebar.groupSecurity : en.sidebar.groupSecurity),
      );
      expect(security?.items.map((item) => item.href)).toEqual(SECURITY_HREFS);
    }
  });

  it("keeps Automation child routes and order including RSS Feeds", () => {
    for (const lang of ["en", "tr"] as const) {
      const automation = getSidebarGroups(lang).find(
        (group) =>
          group.title ===
          (lang === "tr" ? tr.sidebar.groupAutomation : en.sidebar.groupAutomation),
      );
      expect(automation?.items.map((item) => item.href)).toEqual(AUTOMATION_HREFS);
    }
  });

  it("places RSS Feeds once under Automation with the same route and icon", () => {
    for (const lang of ["en", "tr"] as const) {
      const groups = getSidebarGroups(lang);
      const automationTitle =
        lang === "tr" ? tr.sidebar.groupAutomation : en.sidebar.groupAutomation;
      const messagesTitle =
        lang === "tr" ? tr.sidebar.groupMessages : en.sidebar.groupMessages;
      const matches = groups.flatMap((group) =>
        group.items
          .filter((item) => item.href === RSS_HREF)
          .map((item) => ({ group: group.title, item })),
      );
      expect(matches).toHaveLength(1);
      expect(matches[0]?.group).toBe(automationTitle);
      expect(matches[0]?.item.icon).toEqual(cilNotes);
      expect(itemByHref(lang, RSS_HREF)?.label).toBe(
        lang === "tr" ? tr.sidebar.rssFeeds : en.sidebar.rssFeeds,
      );

      const messages = groups.find((group) => group.title === messagesTitle);
      expect(messages?.items.map((item) => item.href)).toEqual(MESSAGES_HREFS);
      expect(messages?.items.some((item) => item.href === RSS_HREF)).toBe(
        false,
      );
    }
  });
});

describe("command palette page rows", () => {
  it("reuses English sidebar labels for dashboard and embed library", () => {
    const entries = getSearchEntries("en");
    expect(entries.find((e) => e.id === "page:dashboard")?.label).toBe(
      "Dashboard",
    );
    expect(
      entries.find((e) => e.id === "page:messages.embed-messages")?.label,
    ).toBe("Embed Library");
  });

  it("reuses Turkish sidebar labels for dashboard and embed library", () => {
    const entries = getSearchEntries("tr");
    expect(entries.find((e) => e.id === "page:dashboard")?.label).toBe(
      "Genel Bakış",
    );
    expect(
      entries.find((e) => e.id === "page:messages.embed-messages")?.label,
    ).toBe("Embed Kitaplığı");
  });
});
