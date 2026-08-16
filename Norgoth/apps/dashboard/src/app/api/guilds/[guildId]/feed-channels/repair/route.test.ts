import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("Top Trending repair proxy", () => {
  it("forwards Origin and Referer so FastAPI CSRF can allow the dashboard", () => {
    const src = readFileSync(resolve(__dirname, "route.ts"), "utf8");
    expect(src).toContain("headers.origin = origin");
    expect(src).toContain("headers.referer = referer");
    expect(src).toContain("request.headers.get(\"cookie\")");
  });
});
