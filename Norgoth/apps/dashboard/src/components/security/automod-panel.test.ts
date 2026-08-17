import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { DEFAULT_AUTOMOD_CONFIG } from "@/stores/automod-store";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";

const panelPath = resolve(__dirname, "automod-panel.tsx");

describe("Auto Moderation format-channel cards", () => {
  const src = readFileSync(panelPath, "utf8");

  it("adds Image Only and Link Only mini-cards with independent toggles", () => {
    expect(src).toContain('activeModal === "image_only"');
    expect(src).toContain('activeModal === "link_only"');
    expect(src).toContain("d.imageOnlyTitle");
    expect(src).toContain("d.linkOnlyTitle");
    expect(src).toContain("config.image_only_enabled");
    expect(src).toContain("config.link_only_enabled");
    expect(src).toContain("setActiveModal(\"image_only\")");
    expect(src).toContain("setActiveModal(\"link_only\")");
  });

  it("keeps toggle clicks from wrapping the card in a second onClick", () => {
    expect(src).toContain("onToggle={(checked) => {");
    expect(src).toContain("norgoth-mini-card");
    expect(src).toContain("ChannelPickerToolbar");
  });

  it("opens the modal instead of enabling when no channel is selected", () => {
    expect(src).toContain("config.image_only_channel_ids.length === 0");
    expect(src).toContain("config.link_only_channel_ids.length === 0");
    expect(src).toContain("setActiveModal(\"image_only\")");
    expect(src).toContain("setActiveModal(\"link_only\")");
  });

  it("uses the shared Refresh Channels toolbar", () => {
    expect(src).toContain("FormatChannelPicker");
    expect(src).toContain("label={d.imageOnlyChannels}");
    expect(src).toContain("label={d.linkOnlyChannels}");
    expect(src).toContain("ChannelPickerToolbar");
  });
});

describe("Auto Moderation format-channel copy", () => {
  it("keeps English and Turkish titles in sync", () => {
    expect(en.autoModPage.imageOnlyTitle).toBe("Image Only Channel");
    expect(tr.autoModPage.imageOnlyTitle).toBe("Yalnızca Görsel Kanalı");
    expect(en.autoModPage.linkOnlyTitle).toBe("Link Only Channel");
    expect(tr.autoModPage.linkOnlyTitle).toBe("Yalnızca Bağlantı Kanalı");
    expect(en.autoModPage.conflictChannels.length).toBeGreaterThan(0);
    expect(tr.autoModPage.conflictChannels.length).toBeGreaterThan(0);
  });

  it("defaults format rules off with empty channel lists", () => {
    expect(DEFAULT_AUTOMOD_CONFIG.image_only_enabled).toBe(false);
    expect(DEFAULT_AUTOMOD_CONFIG.link_only_enabled).toBe(false);
    expect(DEFAULT_AUTOMOD_CONFIG.image_only_channel_ids).toEqual([]);
    expect(DEFAULT_AUTOMOD_CONFIG.link_only_channel_ids).toEqual([]);
  });
});
