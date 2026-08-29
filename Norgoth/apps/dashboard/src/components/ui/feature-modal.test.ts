import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("FeatureConfigurationModal overflow", () => {
  it("exposes optional scrollable and split-pane class names", () => {
    const src = readFileSync(resolve(__dirname, "feature-modal.tsx"), "utf8");
    expect(src).toContain("scrollable = true");
    expect(src).toContain("dialogClassName");
    expect(src).toContain("bodyClassName");
    expect(src).toContain("scrollable={scrollable}");
    expect(src).toContain("shouldInvokeModalClose");
    expect(src).toContain("handleClose");
    expect(src).toContain('role="alert"');
    expect(src).toContain("scrollIntoView");
    expect(src).toContain("errorSummaryLabel");
  });
});
