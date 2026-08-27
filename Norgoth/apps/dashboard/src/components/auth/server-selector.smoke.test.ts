import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const selectorPath = resolve(import.meta.dirname, "server-selector.tsx");
const cardPath = resolve(import.meta.dirname, "server-guild-card.tsx");
const shellPath = resolve(import.meta.dirname, "../layout/app-shell.tsx");

describe("server selector install status smoke", () => {
  it("hosts full-bleed ambient on AppShell and content-only max-width container", () => {
    const shell = readFileSync(shellPath, "utf8");
    const selector = readFileSync(selectorPath, "utf8");

    expect(shell).toContain("norgoth-server-selector-ambient");
    expect(shell).toContain("norgoth-server-selector min-vh-100 d-flex flex-column");
    expect(selector).toContain("norgoth-server-selector-content");
    expect(selector).not.toContain("norgoth-server-selector-ambient");
    expect(selector).toContain("PageHeader");
    expect(selector).toContain("resolveSetupState");
    expect(selector).toContain("target?.bot_installed");
    expect(selector).not.toContain("norgoth-server-summary");
    expect(selector).not.toContain("summaryInstalled");
    expect(selector).not.toContain("installGuidance");
    expect(selector).not.toContain("notConfigured");
    expect(selector).not.toContain("continueSetup");
    expect(selector).not.toContain('"not_configured"');
  });

  it("centers pagination controls without left pageOf text", () => {
    const source = readFileSync(selectorPath, "utf8");
    expect(source).toContain("justify-content-center");
    expect(source).toContain("aria-label={pageLabel}");
    expect(source).not.toContain("justify-content-between");
    expect(source).not.toMatch(
      /<span className="small text-body-secondary">\s*\{t\.pageOf/,
    );
  });

  it("ServerGuildCard uses Manage success and Install primary actions", () => {
    const source = readFileSync(cardPath, "utf8");
    expect(source).toContain('data-install={installAttr}');
    expect(source).toContain("var(--cui-success)");
    expect(source).toContain("var(--cui-danger)");
    expect(source).toContain('role="group"');
    expect(source).toContain("btn-success");
    expect(source).toContain("btn-primary");
    expect(source).toContain("copy.manage");
    expect(source).toContain("justify-content-center");
    expect(source).toContain("mt-auto");
    expect(source).not.toContain("copy.open");
    expect(source).not.toContain("notConfigured");
    expect(source).not.toContain("continueSetup");
  });
});
