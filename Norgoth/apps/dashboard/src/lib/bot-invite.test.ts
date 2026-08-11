import { describe, expect, it } from "vitest";
import { botInviteHref } from "./bot-invite";

describe("botInviteHref", () => {
  it("builds a generic invite without guild_id", () => {
    expect(botInviteHref()).toBe("/norgoth-api/api/v1/oauth/discord/bot-invite");
  });

  it("appends guild_id for a selected server", () => {
    expect(botInviteHref("123456789012345678")).toBe(
      "/norgoth-api/api/v1/oauth/discord/bot-invite?guild_id=123456789012345678",
    );
  });
});
