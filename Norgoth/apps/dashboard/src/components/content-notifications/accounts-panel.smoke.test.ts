import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("AccountsPanel CN preview", () => {
  it("passes webhook embeds into MessagePreview embed mode without placeholders", () => {
    const src = readFileSync(
      resolve(__dirname, "account-editor-modal.tsx"),
      "utf8",
    );
    expect(src).toContain("webhookEmbedToPreview");
    expect(src).toContain('mode="embed"');
    expect(src).toContain("showContentWithEmbed");
    expect(src).not.toContain("showImagePlaceholders");
    expect(src).toContain("destination_channel_id");
    expect(src).toContain("event_types");
    expect(src).toContain("enabled");
    expect(src).not.toContain("Premium");
    expect(src).toContain("readOnly");
    expect(src).toContain("setResolved(null)");
    expect(src).toContain("resolveGeneration");
    expect(src).toContain("disabled={saving || resolving || !url.trim()}");
    expect(src).not.toContain("avatar_url:");
    const panelSrc = readFileSync(
      resolve(__dirname, "accounts-panel.tsx"),
      "utf8",
    );
    expect(panelSrc).toContain("row.source?.avatar_url");
    expect(panelSrc).not.toContain("resolveAccount(");
  });
});

describe("CN landing header", () => {
  it("opens inventory panels from buttons instead of template links", () => {
    const page = readFileSync(
      resolve(
        __dirname,
        "../../app/[lang]/(app)/messages/content-notifications/page.tsx",
      ),
      "utf8",
    );
    const actions = readFileSync(
      resolve(__dirname, "header-actions.tsx"),
      "utf8",
    );
    expect(page).not.toContain('href={`/${lang}/messages/content-notifications/templates`}');
    expect(page).toContain("ContentNotificationsHeaderActions");
    expect(actions).not.toContain("next/link");
    expect(actions).toContain('panel: "templates"');
    expect(actions).toContain("Button");
  });
});

describe("CN store wiring", () => {
  it("paginates accounts and exposes update helpers", () => {
    const src = readFileSync(
      resolve(__dirname, "../../stores/content-notifications-store.ts"),
      "utf8",
    );
    expect(src).toContain("accountsListQuery");
    expect(src).toContain("updateAccount");
    expect(src).toContain("updateTemplate");
    expect(src).toContain("updateStyle");
    expect(src).toContain("analytics?days=");
    expect(src).toContain("method: \"PATCH\"");
    expect(src).toContain("if (!response.ok)");
  });
});

describe("CN template cards", () => {
  it("places compact delete in a bottom-right footer", () => {
    const src = readFileSync(
      resolve(__dirname, "templates-panel.tsx"),
      "utf8",
    );
    expect(src).toContain("d-flex flex-column");
    expect(src).toContain("justify-content-end");
    expect(src).toContain("cilTrash");
    expect(src).toContain("deleteTemplateAria");
    expect(src).toContain("deletingId");
    expect(src).toContain("window.confirm");
    expect(src).toContain("deleteTemplateConfirm");
    expect(src).not.toContain("justify-content-between gap-3");
  });
});

describe("CN sender style cards", () => {
  it("places edit immediately left of delete and expands one editor", () => {
    const src = readFileSync(
      resolve(__dirname, "sender-styles-panel.tsx"),
      "utf8",
    );
    expect(src.indexOf("cilPencil")).toBeLessThan(src.indexOf("cilTrash"));
    expect(src).toContain("editingId");
    expect(src).toContain("updateStyle");
    expect(src).toContain("cancelEdit");
    expect(src).toContain("saveChanges");
    expect(src).toContain("SenderStyleAvatar");
    expect(src).not.toContain("next/image");
    expect(src).toContain("confirmDirtyClose");
  });
});

describe("CN account editor sender style", () => {
  it("explains that a style must be selected for webhook identity", () => {
    const src = readFileSync(
      resolve(__dirname, "account-editor-modal.tsx"),
      "utf8",
    );
    expect(src).toContain("senderStyleMustSelect");
  });
});
