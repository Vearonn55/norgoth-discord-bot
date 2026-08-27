import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const selectorPath = resolve(import.meta.dirname, "server-selector.tsx");
const cardPath = resolve(import.meta.dirname, "server-guild-card.tsx");

describe("server selector install status smoke", () => {
  it("uses PageHeader, install summary metrics, and bot_installed awaiting", () => {
    const source = readFileSync(selectorPath, "utf8");
    expect(source).toContain("PageHeader");
    expect(source).toContain("norgoth-server-selector-ambient");
    expect(source).toContain("norgoth-server-summary");
    expect(source).toContain("summaryInstalled");
    expect(source).toContain("installGuidance");
    expect(source).toContain("resolveSetupState");
    expect(source).toContain("target?.bot_installed");
    expect(source).not.toContain("notConfigured");
    expect(source).not.toContain("continueSetup");
    expect(source).not.toContain('"not_configured"');
  });

  it("ServerGuildCard uses binary install accents and separates install root", () => {
    const source = readFileSync(cardPath, "utf8");
    expect(source).toContain('data-install={installAttr}');
    expect(source).toContain("var(--cui-success)");
    expect(source).toContain("var(--cui-danger)");
    expect(source).toContain('role="group"');
    expect(source).toContain("justify-content-center");
    expect(source).toContain("mt-auto");
    expect(source).not.toContain("notConfigured");
    expect(source).not.toContain("continueSetup");
  });
});
