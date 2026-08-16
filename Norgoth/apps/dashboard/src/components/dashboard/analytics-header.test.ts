import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("Analytics PageHeader icon", () => {
  it("uses the shared cilChartLine icon on the analytics dashboard", () => {
    const src = readFileSync(
      resolve(__dirname, "analytics-dashboard.tsx"),
      "utf8",
    );
    expect(src).toContain("cilChartLine");
    expect(src).toContain("icon={<Icon icon={cilChartLine} size=\"xl\" />}");
  });
});
