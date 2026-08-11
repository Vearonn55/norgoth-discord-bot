import { afterEach, describe, expect, it } from "vitest";
import { dashboardUrl, getDashboardOrigin } from "@/lib/dashboard-origin";

const ENV_KEYS = [
  "NORGOTH_DASHBOARD_URL",
  "NEXT_PUBLIC_DASHBOARD_URL",
] as const;

const originalEnv: Record<string, string | undefined> = {};

function clearDashboardEnv() {
  for (const key of ENV_KEYS) {
    originalEnv[key] = process.env[key];
    delete process.env[key];
  }
}

function restoreDashboardEnv() {
  for (const key of ENV_KEYS) {
    const value = originalEnv[key];
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }
}

afterEach(() => {
  restoreDashboardEnv();
});

describe("getDashboardOrigin / dashboardUrl", () => {
  it("uses NORGOTH_DASHBOARD_URL for production redirects", () => {
    clearDashboardEnv();
    process.env.NORGOTH_DASHBOARD_URL = "https://www.norbot.io";

    expect(getDashboardOrigin("http://0.0.0.0:3000/api/auth/complete")).toBe(
      "https://www.norbot.io",
    );
    expect(dashboardUrl("/en/servers", "http://0.0.0.0:3000/api/auth/complete").href).toBe(
      "https://www.norbot.io/en/servers",
    );
    expect(dashboardUrl("/tr/servers", "http://0.0.0.0:3000/api/auth/complete").href).toBe(
      "https://www.norbot.io/tr/servers",
    );
  });

  it("falls back to NEXT_PUBLIC_DASHBOARD_URL when NORGOTH_DASHBOARD_URL is unset", () => {
    clearDashboardEnv();
    process.env.NEXT_PUBLIC_DASHBOARD_URL = "https://www.norbot.io/";

    expect(getDashboardOrigin()).toBe("https://www.norbot.io");
  });

  it("does not emit 0.0.0.0 even when the request origin is the container bind address", () => {
    clearDashboardEnv();
    process.env.NORGOTH_DASHBOARD_URL = "https://www.norbot.io";

    const target = dashboardUrl(
      "/en/servers",
      "http://0.0.0.0:3000/api/auth/complete?lang=en&code=abc",
    );
    expect(target.origin).toBe("https://www.norbot.io");
    expect(target.href).not.toContain("0.0.0.0");
  });

  it("preserves local request origin when no dashboard URL is configured", () => {
    clearDashboardEnv();

    expect(
      getDashboardOrigin("http://127.0.0.1:3000/api/auth/complete"),
    ).toBe("http://127.0.0.1:3000");
    expect(
      dashboardUrl("/en/login?error=exchange", "http://localhost:3000/x").href,
    ).toBe("http://localhost:3000/en/login?error=exchange");
  });

  it("falls back to 127.0.0.1 when request origin is 0.0.0.0 and env is unset", () => {
    clearDashboardEnv();

    expect(getDashboardOrigin("http://0.0.0.0:3000/api/auth/complete")).toBe(
      "http://127.0.0.1:3000",
    );
  });

  it("ignores malformed or non-http configured URLs", () => {
    clearDashboardEnv();
    process.env.NORGOTH_DASHBOARD_URL = "not a url";
    process.env.NEXT_PUBLIC_DASHBOARD_URL = "ftp://evil.example";

    expect(getDashboardOrigin("http://127.0.0.1:3000/path")).toBe(
      "http://127.0.0.1:3000",
    );
  });

  it("rejects configured 0.0.0.0 dashboard URLs", () => {
    clearDashboardEnv();
    process.env.NORGOTH_DASHBOARD_URL = "http://0.0.0.0:3000";

    expect(getDashboardOrigin("http://127.0.0.1:3000/path")).toBe(
      "http://127.0.0.1:3000",
    );
  });
});
