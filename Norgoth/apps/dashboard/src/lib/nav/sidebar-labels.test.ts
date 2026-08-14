import { describe, expect, it } from "vitest";
import { getSidebarGroups } from "@/components/navigation/sidebar";
import { getSearchEntries } from "@/lib/nav/search-entries";

function itemByHref(lang: string, href: string) {
  return getSidebarGroups(lang)
    .flatMap((group) => group.items)
    .find((item) => item.href === href);
}

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
