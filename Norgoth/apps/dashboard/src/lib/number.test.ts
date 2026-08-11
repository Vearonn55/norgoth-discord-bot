import { describe, expect, it } from "vitest";
import { EMPTY_NUMBER_PLACEHOLDER, formatNumber } from "@/lib/number";

describe("formatNumber", () => {
  it("groups thousands using the en locale", () => {
    expect(formatNumber(12345, "en")).toBe("12,345");
  });

  it("groups thousands using the tr locale", () => {
    expect(formatNumber(12345, "tr")).toBe("12.345");
  });

  it("returns a placeholder for missing values", () => {
    expect(formatNumber(null, "en")).toBe(EMPTY_NUMBER_PLACEHOLDER);
    expect(formatNumber(undefined, "en")).toBe(EMPTY_NUMBER_PLACEHOLDER);
    expect(formatNumber(Number.NaN, "en")).toBe(EMPTY_NUMBER_PLACEHOLDER);
  });
});
