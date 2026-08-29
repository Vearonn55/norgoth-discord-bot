import { describe, expect, it } from "vitest";

type ManualReviewItem = {
  display_name: string | null;
  username: string | null;
  avatar_url: string | null;
  discord_user_id: string;
};

function memberName(item: ManualReviewItem, unavailableMember: string): string {
  if (item.display_name) return item.display_name;
  if (item.username) return item.username;
  return unavailableMember;
}

describe("manual verification member display", () => {
  it("uses unavailable member label when profile data is missing", () => {
    const row: ManualReviewItem = {
      display_name: null,
      username: null,
      avatar_url: null,
      discord_user_id: "123456789012345678",
    };

    expect(memberName(row, "Unavailable member")).toBe("Unavailable member");
  });

  it("prefers display name when present", () => {
    const row: ManualReviewItem = {
      display_name: "Kaan",
      username: "kaan",
      avatar_url: null,
      discord_user_id: "123456789012345678",
    };

    expect(memberName(row, "Unavailable member")).toBe("Kaan");
  });
});
