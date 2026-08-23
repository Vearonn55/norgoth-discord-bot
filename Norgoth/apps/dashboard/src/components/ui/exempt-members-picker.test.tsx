import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ExemptMembersPicker } from "@/components/ui/exempt-members-picker";

vi.mock("@/lib/locale-dict", () => ({
  useLocaleDict: () => ({
    common: { retry: "Retry" },
    serverSelector: {
      previousPage: "Previous",
      nextPage: "Next",
    },
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
      membersLoading: "Loading members…",
      membersLoadFailed: "Could not load guild members.",
      membersSnapshotMissing: "No member snapshot available yet.",
      membersEmpty: "No members in the server snapshot.",
      membersNoResults: "No members match your search.",
      membersPageSummary: "{start}–{end} of {total} members · {selected} selected",
      membersPaginationAria: "Exempt members list pagination",
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
        members: [
          {
            id: "1000",
            name: "member-0",
            display_name: "Member 0",
            bot: false,
          },
        ],
        included_members: [
          {
            id: "1149",
            name: "member-149",
            display_name: "Member 149",
            bot: false,
          },
        ],
        pagination: {
          offset: 0,
          limit: 10,
          total: 150,
          total_pages: 15,
          page: 1,
          has_previous: false,
          has_next: true,
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("uses server-side pagination query params", () => {
    const src = readFileSync(pickerPath, "utf8");
    expect(src).toContain("include_member_ids");
    expect(src).toContain("norgoth-pagination-bar");
    expect(src).not.toContain(".slice(0, 100)");
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
    expect(src).toContain("membersLoading");
  });
});
