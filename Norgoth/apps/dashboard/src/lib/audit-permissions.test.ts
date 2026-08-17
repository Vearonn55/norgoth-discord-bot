import { describe, expect, it } from "vitest";
import { formatAuditValue } from "@/lib/audit-permissions";
import { getLocaleDict } from "@/lib/locale-format";
import { auditPermissionLabel } from "@/lib/audit-permissions";

describe("formatAuditValue", () => {
  it("keeps markup as plain text", () => {
    expect(formatAuditValue("<img src=x onerror=alert(1)>")).toBe(
      "<img src=x onerror=alert(1)>",
    );
    expect(formatAuditValue("<script>alert(1)</script>")).toContain("<script>");
  });
});

describe("auditPermissionLabel", () => {
  it("uses the English mapping and a safe unknown fallback", () => {
    const en = getLocaleDict("en");
    const tr = getLocaleDict("tr");
    expect(auditPermissionLabel(en, "manage_roles")).toBe("Manage Roles");
    expect(auditPermissionLabel(tr, "manage_roles")).toBe("Rolleri Yönet");
    expect(auditPermissionLabel(en, "unknown", "0x1")).toBe(
      "Unknown permission (0x1)",
    );
  });
});
