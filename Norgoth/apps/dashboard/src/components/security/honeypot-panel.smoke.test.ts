import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const panelPath = resolve(
  import.meta.dirname,
  "honeypot-panel.tsx"
);

describe("HoneypotPanel layout smoke", () => {
  it("uses equalized mini cards and ExemptMembersPicker in exemptions modal", () => {
    const src = readFileSync(panelPath, "utf8");
    expect(src).toContain('className="col h-100"');
    expect(src).toContain("equalizeFooter");
    expect(src).toContain("ExemptMembersPicker");
    expect(src).not.toContain("MemberSelect");
  });
});
