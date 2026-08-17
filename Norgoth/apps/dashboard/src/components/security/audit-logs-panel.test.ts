import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";
import {
  auditFieldLabel,
  auditPermissionLabel,
  formatAuditValue,
} from "@/lib/audit-permissions";
import { getLocaleDict } from "@/lib/locale-format";

const panelPath = resolve(__dirname, "audit-logs-panel.tsx");
const detailsPath = resolve(__dirname, "audit-change-details.tsx");
const tablePath = resolve(__dirname, "../ui/data-table.tsx");

describe("Audit Logs change details", () => {
  const panel = readFileSync(panelPath, "utf8");
  const details = readFileSync(detailsPath, "utf8");
  const table = readFileSync(tablePath, "utf8");

  it("opens event details from the expandable row", () => {
    expect(panel).toContain("AuditChangeDetails");
    expect(panel).toContain("eventId={row.eventId}");
    expect(panel).toContain('row.source === "event"');
  });

  it("renders previous and new values without HTML injection", () => {
    expect(details).toContain("formatAuditValue(change.previous)");
    expect(details).toContain("formatAuditValue(change.next)");
    expect(details).not.toContain("dangerouslySetInnerHTML");
    expect(details).toContain("norgoth-audit-wrap");
    expect(details).toContain("d.legacyDetail");
    expect(details).toContain("d.detailError");
    expect(details).toContain("d.loadingShort");
  });

  it("keeps DataTable expansion keyboard accessible and ignores nested controls", () => {
    expect(table).toContain('role={expandable ? "button" : undefined}');
    expect(table).toContain("aria-expanded");
    expect(table).toContain("isInteractiveTarget");
    expect(table).toContain("Enter");
    expect(table).toContain('event.key !== " "');
  });

  it("keeps English and Turkish audit labels in sync", () => {
    const enKeys = Object.keys(en.auditLogsPage).sort();
    const trKeys = Object.keys(tr.auditLogsPage).sort();
    expect(trKeys).toEqual(enKeys);
    const enPerms = Object.keys(en.auditPermissions).sort();
    const trPerms = Object.keys(tr.auditPermissions).sort();
    expect(trPerms).toEqual(enPerms);
    expect(en.auditLogsPage.legacyDetail).toContain("not recorded");
    expect(tr.auditLogsPage.legacyDetail).toContain("kaydedilmedi");
  });

  it("localizes permission names and unknown bits", () => {
    const dict = getLocaleDict("en");
    expect(auditPermissionLabel(dict, "view_channel")).toBe("View Channel");
    expect(auditPermissionLabel(dict, "unknown", "0xabc")).toContain("0xabc");
    expect(auditFieldLabel(dict, "topic")).toBe("Topic");
    expect(formatAuditValue({ id: "1", name: "general" })).toBe("general (1)");
  });
});
