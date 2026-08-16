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
    expect(src).toContain("analytics?days=");
  });
});
