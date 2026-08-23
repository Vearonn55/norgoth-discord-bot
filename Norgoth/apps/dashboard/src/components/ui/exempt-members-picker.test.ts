import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ExemptMembersPicker } from "@/components/ui/exempt-members-picker";

vi.mock("@/lib/locale-dict", () => ({
  useLocaleDict: () => ({
    honeypotPage: {
      currentlyExemptTitle: "Currently Exempt ({count})",
      currentlyExemptEmpty: "No exempt members configured.",
      exemptBadge: "Exempt",
      exemptMembersOnlyFilter: "Exempt members only",
      searchMembersPlaceholder: "Search members…",
      unavailableMember: "Unavailable member",
      unavailableMemberHint: "No longer in snapshot.",
      removeExemptMember: "Remove exempt member {name}",
      exemptSelectionAdded: "Added {name} to exemptions",
      exemptSelectionRemoved: "Removed {name} from exemptions",
      exemptMembersEmpty: "No members match your search.",
      exemptMembers: "Exempt Members",
      remove: "Remove",
    },
  }),
  formatDict: (template: string, values: Record<string, string | number>) =>
    template.replace(/\{(\w+)\}/g, (_match, key: string) =>
      String(values[key] ?? "")
    ),
}));

const pickerPath = resolve(
  import.meta.dirname,
  "exempt-members-picker.tsx"
);

describe("ExemptMembersPicker", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        members: Array.from({ length: 150 }, (_item, index) => ({
          id: String(1000 + index),
          name: `member-${index}`,
          display_name: `Member ${index}`,
          bot: false,
        })),
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("always includes selected IDs in list source even outside top 100 window", () => {
    const src = readFileSync(pickerPath, "utf8");
    expect(src).toContain("selectedRows");
    expect(src).toContain(".slice(0, 100)");
  });

  it("shows selected IDs in summary", () => {
    const html = renderToStaticMarkup(
      <ExemptMembersPicker
        guildId="guild-1"
        values={["1000", "1149"]}
        onChange={() => undefined}
      />
    );
    expect(html).toContain("1149");
    expect(html).toContain("1000");
    expect(html).toContain("Currently Exempt (2)");
  });

  it("renders unavailable member row for stale IDs", () => {
    const html = renderToStaticMarkup(
      <ExemptMembersPicker
        guildId="guild-1"
        values={["999999999999999999"]}
        onChange={() => undefined}
      />
    );
    expect(html).toContain("Unavailable member");
    expect(html).toContain("999999999999999999");
  });

  it("includes accessible listbox markup in source", () => {
    const src = readFileSync(pickerPath, "utf8");
    expect(src).toContain('role="listbox"');
    expect(src).toContain('aria-live="polite"');
    expect(src).toContain("norgoth-member-row-selected");
  });
});
