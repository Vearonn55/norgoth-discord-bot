/** Smoke coverage for Embed Draft Creator create CTA label and layout classes. */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const creatorPath = resolve(
  __dirname,
  "../components/embed-messages/embed-draft-creator.tsx"
);
const panelPath = resolve(
  __dirname,
  "../components/embed-messages/embed-messages-panel.tsx"
);
const ticketsPath = resolve(
  __dirname,
  "../components/community/tickets-panel.tsx"
);
const miniCardPath = resolve(
  __dirname,
  "../components/ui/mini-feature-card.tsx"
);

describe("embed draft creator layout + save draft", () => {
  it("renders preview column before the editor column", () => {
    const src = readFileSync(creatorPath, "utf8");
    const previewIdx = src.indexOf("previewColClass");
    const editorIdx = src.indexOf("editorColClass");
    // In the JSX return, preview column is rendered before editor.
    const jsxPreview = src.indexOf("{showPreviewColumn ? (");
    const jsxEditor = src.indexOf("className={editorColClass}");
    expect(jsxPreview).toBeGreaterThan(-1);
    expect(jsxEditor).toBeGreaterThan(jsxPreview);
    expect(src).toContain('createLabel ?? "Save Draft"');
    expect(src).toContain("norgoth-embed-creator-preview");
    expect(previewIdx).toBeGreaterThan(-1);
    expect(editorIdx).toBeGreaterThan(-1);
  });

  it("New Embed modal closes via onCreated and uses Save Draft", () => {
    const src = readFileSync(panelPath, "utf8");
    expect(src).toContain('createLabel="Save Draft"');
    expect(src).toContain("setCreateOpen(false)");
    expect(src).not.toMatch(/scrollable\s*\n\s*backdrop/);
  });
});

describe("ticket panel embed workflow + layout", () => {
  it("exposes Select From Draft / Create New and side-by-side support layout", () => {
    const src = readFileSync(ticketsPath, "utf8");
    expect(src).toContain("Select From Draft");
    expect(src).toContain("Create New");
    expect(src).toContain("TicketPanelPreview");
    expect(src).toContain("EmbedDraftCreator");
    expect(src).toContain("col-lg-4");
    expect(src).toContain("col-lg-8");
    expect(src).toContain("Ticket Support Role");
    expect(src).toContain("Message inside new tickets");
    expect(src).toContain("RichMessageEditor");
    expect(src).toContain("ticket-welcome-editor");
  });
});

describe("mini feature card equalization", () => {
  it("applies h-100 and description clamp class", () => {
    const src = readFileSync(miniCardPath, "utf8");
    expect(src).toContain("h-100");
    expect(src).toContain("norgoth-mini-card-description");
  });
});
