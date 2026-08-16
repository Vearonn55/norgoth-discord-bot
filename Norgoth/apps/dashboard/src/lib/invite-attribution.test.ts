import { describe, expect, it } from "vitest";
import { invitedByLabel } from "./invite-attribution";

const copy = {
  vanityUrl: "vanity URL",
  unknown: "unknown",
  attributionDeleted: "deleted invite",
  attributionAmbiguous: "ambiguous",
  attributionUnavailable: "unavailable",
};

describe("invitedByLabel", () => {
  it("prefers a live inviter name", () => {
    expect(
      invitedByLabel(
        {
          inviter_name: "Alice",
          inviter_id: "1",
          code: "abc",
          attribution: "attributed",
        },
        copy,
      ),
    ).toBe("Alice");
  });

  it("labels vanity joins without inventing an inviter", () => {
    expect(
      invitedByLabel(
        {
          inviter_name: null,
          inviter_id: null,
          code: "vanity",
          attribution: "vanity",
        },
        copy,
      ),
    ).toBe("vanity URL");
  });

  it("keeps legacy unknown rows without inviter_id as unknown", () => {
    expect(
      invitedByLabel(
        {
          inviter_name: null,
          inviter_id: null,
          code: null,
          attribution: null,
        },
        copy,
      ),
    ).toBe("unknown");
  });

  it("surfaces honest fallbacks for deleted, ambiguous, and unavailable", () => {
    expect(
      invitedByLabel(
        {
          inviter_name: null,
          inviter_id: null,
          code: "gone",
          attribution: "deleted",
        },
        copy,
      ),
    ).toBe("deleted invite");
    expect(
      invitedByLabel(
        {
          inviter_name: null,
          inviter_id: null,
          code: null,
          attribution: "ambiguous",
        },
        copy,
      ),
    ).toBe("ambiguous");
    expect(
      invitedByLabel(
        {
          inviter_name: null,
          inviter_id: null,
          code: null,
          attribution: "unavailable",
        },
        copy,
      ),
    ).toBe("unavailable");
  });
});
