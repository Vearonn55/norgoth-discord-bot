import { describe, expect, it } from "vitest";
import {
  EMPTY_DATE_PLACEHOLDER,
  formatDateTime,
  formatDateTimeShort,
} from "@/lib/datetime";

const ISO = "2026-08-09T03:42:17.348922+00:00";

describe("formatDateTime", () => {
  it("renders a localized date with seconds for en", () => {
    const out = formatDateTime(ISO, "en");
    expect(out).not.toBe(EMPTY_DATE_PLACEHOLDER);
    expect(out).not.toContain("T");
    expect(out).toMatch(/2026/);
    expect(out).toMatch(/ - /);
    // HH:mm:ss present
    expect(out).toMatch(/\d{2}:\d{2}:\d{2}/);
  });

  it("renders a localized string with seconds for tr", () => {
    const out = formatDateTime(ISO, "tr");
    expect(out).not.toBe(EMPTY_DATE_PLACEHOLDER);
    expect(out).not.toContain("T");
    expect(out).toMatch(/2026/);
    expect(out).toMatch(/\d{2}:\d{2}:\d{2}/);
  });

  it("falls back gracefully for null/invalid input", () => {
    expect(formatDateTime(null, "en")).toBe(EMPTY_DATE_PLACEHOLDER);
    expect(formatDateTime(undefined, "en")).toBe(EMPTY_DATE_PLACEHOLDER);
    expect(formatDateTime("not-a-date", "en")).toBe(EMPTY_DATE_PLACEHOLDER);
  });

  it("represents the same instant regardless of locale", () => {
    expect(formatDateTime(ISO, "en")).not.toBe(formatDateTime(ISO, "tr"));
  });
});

describe("formatDateTimeShort", () => {
  it("renders compact date + time with seconds", () => {
    const out = formatDateTimeShort(ISO, "tr");
    expect(out).not.toContain("T");
    expect(out).toMatch(/2026/);
    expect(out).toMatch(/\d{2}:\d{2}:\d{2}/);
  });

  it("falls back for invalid input", () => {
    expect(formatDateTimeShort("", "en")).toBe(EMPTY_DATE_PLACEHOLDER);
  });
});
