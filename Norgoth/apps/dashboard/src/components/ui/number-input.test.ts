import { describe, expect, it } from "vitest";

/**
 * Mirror NumberInput commit normalization (string draft until commit).
 * Kept as a pure helper test so we do not mount CoreUI in unit tests.
 */
function normalizeCommitted(
  draft: string,
  {
    defaultValue,
    min,
    max,
  }: { defaultValue: number; min?: number; max?: number }
): number {
  if (draft.trim() === "") return defaultValue;
  const parsed = Number.parseInt(draft, 10);
  if (!Number.isFinite(parsed)) return defaultValue;
  let next = parsed;
  if (min != null) next = Math.max(min, next);
  if (max != null) next = Math.min(max, next);
  return Math.trunc(next);
}

function sanitizeDigits(raw: string): string {
  return raw.replace(/\D/g, "");
}

describe("NumberInput commit semantics", () => {
  it("allows temporary empty then types a replacement", () => {
    let draft = "25";
    draft = sanitizeDigits("");
    expect(draft).toBe("");
    draft = sanitizeDigits("1");
    draft = sanitizeDigits(draft + "0");
    expect(draft).toBe("10");
    expect(
      normalizeCommitted(draft, { defaultValue: 25, min: 1, max: 25 })
    ).toBe(10);
  });

  it("restores field default on empty commit", () => {
    expect(
      normalizeCommitted("", { defaultValue: 25, min: 1, max: 25 })
    ).toBe(25);
    expect(
      normalizeCommitted("", { defaultValue: 5, min: 5, max: 60 })
    ).toBe(5);
  });

  it("rejects alphabetic characters while typing", () => {
    expect(sanitizeDigits("abc")).toBe("");
    expect(sanitizeDigits("12a3")).toBe("123");
  });

  it("supports partial multi-digit typing", () => {
    let draft = "";
    for (const ch of ["1", "10", "100"]) {
      draft = sanitizeDigits(ch);
    }
    expect(draft).toBe("100");
    expect(
      normalizeCommitted(draft, { defaultValue: 10, min: 1, max: 25 })
    ).toBe(25);
  });

  it("does not treat empty as zero via Number", () => {
    expect(Number("")).toBe(0);
    expect(normalizeCommitted("", { defaultValue: 10 })).toBe(10);
  });
});
