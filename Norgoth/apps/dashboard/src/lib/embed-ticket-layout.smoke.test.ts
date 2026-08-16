import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = resolve(__dirname, "..");
const creatorPath = resolve(
  root,
  "components/embed-messages/embed-draft-creator.tsx"
);
const panelPath = resolve(
  root,
  "components/embed-messages/embed-messages-panel.tsx"
);
const ticketsPath = resolve(root, "components/community/tickets-panel.tsx");
const miniCardPath = resolve(root, "components/ui/mini-feature-card.tsx");

describe("embed draft creator layout + save draft", () => {
  it("renders the editor column before the preview column", () => {
    const src = readFileSync(creatorPath, "utf8");
    const previewIdx = src.indexOf("norgoth-embed-creator-preview");
    const editorIdx = src.indexOf("norgoth-embed-creator-editor");
    // Editor left / preview right: formCard is emitted before previewColumn.
    const jsxPreview = src.indexOf("{previewColumn}");
    const jsxEditor = src.indexOf("{formCard}");
    expect(jsxEditor).toBeGreaterThan(-1);
    expect(jsxPreview).toBeGreaterThan(jsxEditor);
    expect(src).toContain("createLabel ?? d.saveDraft");
    expect(src).toContain("norgoth-embed-creator-preview");
    expect(previewIdx).toBeGreaterThan(-1);
    expect(editorIdx).toBeGreaterThan(-1);
  });

  it("New Embed modal closes via onCreated and uses Save Draft", () => {
    const src = readFileSync(panelPath, "utf8");
    expect(src).toContain("createLabel={d.saveDraft}");
    expect(src).toContain("setCreateOpen(false)");
    expect(src).not.toMatch(/scrollable\s*\n\s*backdrop/);
    expect(src).toContain("norgoth-embed-create-modal");
  });
});

describe("ticket panel embed workflow + layout", () => {
  it("exposes Select From Draft / Create New and side-by-side support layout", () => {
    const src = readFileSync(ticketsPath, "utf8");
    expect(src).toContain("d.selectFromDraft");
    expect(src).toContain("d.createNew");
    expect(src).toContain("TicketPanelPreview");
    expect(src).toContain("col-12 col-lg-4");
    expect(src).toContain("col-12 col-lg-8");
    expect(src).toContain("d.supportRoleTitle");
    expect(src).toContain("d.welcomeLabel");
  });
});

describe("mini feature card equalization", () => {
  it("applies h-100 and description clamp class", () => {
    const src = readFileSync(miniCardPath, "utf8");
    expect(src).toContain("h-100");
    expect(src).toContain("norgoth-mini-card-description");
  });
});
