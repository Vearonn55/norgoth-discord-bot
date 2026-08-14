import { describe, expect, it } from "vitest";

import { isSafeHttpUrl } from "@/lib/discord-markdown";

describe("isSafeHttpUrl", () => {
  it("allows http and https", () => {
    expect(isSafeHttpUrl("https://norbot.io/docs")).toBe(true);
    expect(isSafeHttpUrl("http://example.com")).toBe(true);
  });

  it("rejects javascript and data URLs", () => {
    expect(isSafeHttpUrl("javascript:alert(1)")).toBe(false);
    expect(isSafeHttpUrl("data:text/html,hi")).toBe(false);
    expect(isSafeHttpUrl("not-a-url")).toBe(false);
  });
});
