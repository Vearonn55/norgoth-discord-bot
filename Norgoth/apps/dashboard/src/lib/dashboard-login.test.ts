import { afterEach, describe, expect, it, vi } from "vitest";
import { dashboardLoginHref } from "./dashboard-login";

describe("dashboardLoginHref", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("returns the Discord authorize URL when auth is enforced", () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_ENFORCED", "true");
    expect(dashboardLoginHref("en")).toBe(
      "/norgoth-api/api/v1/oauth/discord/dashboard/authorize?lang=en",
    );
    expect(dashboardLoginHref("tr")).toBe(
      "/norgoth-api/api/v1/oauth/discord/dashboard/authorize?lang=tr",
    );
  });

  it("returns the servers path when auth is bypassed", () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_ENFORCED", "false");
    expect(dashboardLoginHref("en")).toBe("/en/servers");
    expect(dashboardLoginHref("tr")).toBe("/tr/servers");
  });
});
