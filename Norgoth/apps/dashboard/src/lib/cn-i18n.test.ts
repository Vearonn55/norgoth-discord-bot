import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";

describe("content notifications and campaign history i18n", () => {
  it("keeps English leveling and feed copy unchanged", () => {
    expect(en.levelingPage.rankedMembers).toBe("Ranked Members");
    expect(en.levelingPage.rewardRoles).toBe("Reward Roles");
    expect(en.levelingPage.announceCurrent).toBe("Member's channel");
    expect(en.feedChannels.dailySliderTitle).toBe("Feed Refresh Interval");
    expect(en.feedChannelsPage.windowEnabledSuccess).toBe("{window} feed enabled.");
    expect(en.feedChannelsPage.windowDisabledSuccess).toBe(
      "{window} feed disabled.",
    );
    expect(en.feedChannelsPage.windowUpdatedSuccess).toBe("Feed window updated.");
    expect(en.feedChannelsPage.title).toBe("Top Trending");
    expect(en.common.refreshChannels).toBe("Refresh Channels");
    expect(en.common.refreshRoles).toBe("Refresh Roles");
    expect(en.common.refreshRolesSuccess).toBe("Role list updated.");
    expect(en.common.roleUnavailable).toBe("Deleted or no longer available");
    expect(en.common.refreshChannelsSuccess).toBe("Channel list updated.");
    expect(en.common.refreshChannelsError).toBe(
      "Could not refresh channels. Please retry.",
    );
    expect(en.common.channelUnavailable).toBe("Deleted or no longer available");
    expect(en.common.discordRateLimited).toBe(
      "Discord is rate-limiting guild resources. Please retry shortly.",
    );
    expect(en.campaignHistoryPage.metricArchived).toBe("Archived Campaigns");
    expect(en.contentNotifications.historyModalTitle).toBe("History");
    expect(en.contentNotifications.historyPageTitle).toBe("Delivery History");
    expect(en.contentNotifications.kickCapacity).toBe(
      "{count} of {limit} Kick configurations",
    );
    expect(en.contentNotifications.kickDisabledCount).toContain("count toward");
  });

  it("uses the mapped Turkish strings", () => {
    expect(tr.levelingPage.rankedMembers).toBe("Sıralamadaki Üyeler");
    expect(tr.levelingPage.rewardRoles).toBe("Seviye Ödülleri");
    expect(tr.levelingPage.announceCurrent).toBe("Seviye Alınan Kanal");
    expect(tr.levelingPage.levelThresholdScaleHelp).toContain("olarak");
    expect(tr.feedChannels.dailySliderTitle).toBe("Feed Yenileme Aralığı");
    expect(tr.feedChannelsPage.feedCategoryTitle).toBe("Feed Kategorisi");
    expect(tr.feedChannelsPage.windowEnabledSuccess).toBe(
      "{window} feed etkinleştirildi.",
    );
    expect(tr.feedChannelsPage.windowDisabledSuccess).toBe(
      "{window} feed devre dışı bırakıldı.",
    );
    expect(tr.feedChannelsPage.windowUpdatedSuccess).toBe(
      "Feed penceresi güncellendi.",
    );
    expect(tr.common.refreshChannels).toBe("Kanalları Yenile");
    expect(tr.common.refreshRoles).toBe("Rolleri Yenile");
    expect(tr.common.refreshRolesSuccess).toBe("Rol listesi güncellendi.");
    expect(tr.common.refreshChannelsSuccess).toBe("Kanal listesi güncellendi.");
    expect(tr.common.refreshChannelsError).toBe(
      "Kanallar yenilenemedi. Lütfen yeniden deneyin.",
    );
    expect(tr.common.channelUnavailable).toBe("Silindi veya artık uygun değil");
    expect(tr.featureInfo.inviteTracking.description).toContain(
      "davet bağlantılarıyla ilişkilendirir.",
    );
    expect(tr.campaignHistoryPage.metricArchived).toBe("Arşivlenen Kampanyalar");
    expect(tr.campaignHistoryPage.metricDelivered).toBe("Gönderilen Mesajlar");
    expect(tr.campaignHistoryPage.metricFailed).toBe("Başarısız Teslimatlar");
    expect(tr.campaignHistoryPage.metricRetries).toBe("Yeniden Deneme Olayları");
    expect(tr.campaignHistoryPage.exporting).toBe("Dışa aktarılıyor…");
    expect(tr.contentNotifications.historyModalTitle).toBe("Geçmiş");
    expect(tr.contentNotifications.historyPageTitle).toBe("Teslimat Geçmişi");
    expect(tr.contentNotifications.kickCapacity).toBe(
      "{count} / {limit} Kick yapılandırması",
    );
    expect(tr.sidebar.rssFeeds).toBe("RSS Akışları");
  });
});

describe("top trending master toggle", () => {
  it("hides the duplicate title beside the slider and keeps the accessible name", () => {
    const src = readFileSync(
      resolve(__dirname, "../components/community/feed-channels-panel.tsx"),
      "utf8",
    );
    expect(src).toContain("showLabel: false");
    expect(src).toContain("label: d.title");
  });
});

describe("refresh channels action", () => {
  it("keeps labeled refresh copy and reduced-motion CSS", () => {
    const buttonSrc = readFileSync(
      resolve(__dirname, "../components/ui/refresh-channels-button.tsx"),
      "utf8",
    );
    const cssSrc = readFileSync(
      resolve(__dirname, "../app/globals.css"),
      "utf8",
    );
    const selectSrc = readFileSync(
      resolve(__dirname, "../components/ui/channel-select.tsx"),
      "utf8",
    );
    const campaignSrc = readFileSync(
      resolve(__dirname, "../components/campaigns/campaign-wizard.tsx"),
      "utf8",
    );
    expect(buttonSrc).toContain("cilReload");
    expect(buttonSrc).toContain("flex-wrap");
    expect(buttonSrc).toContain("common.refreshChannels");
    expect(buttonSrc).toContain("common.refreshRoles");
    expect(buttonSrc).toContain("aria-live=\"polite\"");
    expect(buttonSrc).toContain("norgoth-refresh-spin");
    expect(buttonSrc.indexOf("aria-live")).toBeLessThan(buttonSrc.indexOf("<Button"));
    expect(cssSrc).toContain("@media (prefers-reduced-motion: reduce)");
    expect(cssSrc).toContain(".norgoth-refresh-spin");
    expect(selectSrc).toContain("channelUnavailable");
    expect(campaignSrc).toContain("RefreshChannelsButton");
    expect(campaignSrc).toContain("RolePickerToolbar");
    expect(campaignSrc).not.toContain("/discord-resources");
  });

  it("places RolePickerToolbar on every role-selection scope", () => {
    const files = [
      "../components/verification/verification-settings-form.tsx",
      "../components/security/automod-panel.tsx",
      "../components/security/honeypot-panel.tsx",
      "../components/messages/rss-feeds-panel.tsx",
      "../components/content-notifications/account-editor-modal.tsx",
      "../components/community/tickets-panel.tsx",
      "../components/community/leveling-panel.tsx",
      "../components/campaigns/campaign-wizard.tsx",
      "../components/automation/role-menus-panel.tsx",
      "../components/automation/automation-settings-panel.tsx",
      "../components/automation/notifications-panel.tsx",
    ];
    for (const relative of files) {
      const src = readFileSync(resolve(__dirname, relative), "utf8");
      expect(src).toMatch(/RolePickerToolbar|RefreshRolesButton/);
    }
    const roleSelectSrc = readFileSync(
      resolve(__dirname, "../components/ui/role-select.tsx"),
      "utf8",
    );
    expect(roleSelectSrc).toContain("roleUnavailable");
  });
});

describe("campaign history toolbar", () => {
  it("does not hardcode English metric labels", () => {
    const src = readFileSync(
      resolve(__dirname, "../components/campaigns/campaign-archive-toolbar.tsx"),
      "utf8",
    );
    expect(src).toContain("campaignHistoryPage");
    expect(src).not.toContain("Archived Campaigns");
    expect(src).not.toContain("Delivered Messages");
    expect(src).not.toContain("Failed Deliveries");
    expect(src).not.toContain("Retry Events");
    expect(src).not.toContain("Exporting…");
  });
});

describe("levels and activity teaser", () => {
  it("removes the leaderboard teaser card and keeps widgets plus load()", () => {
    const panelSrc = readFileSync(
      resolve(__dirname, "../components/community/leveling-panel.tsx"),
      "utf8",
    );
    const leaderboardSrc = readFileSync(
      resolve(__dirname, "../components/community/leaderboard-panel.tsx"),
      "utf8",
    );
    const storeSrc = readFileSync(
      resolve(__dirname, "../stores/leveling-store.ts"),
      "utf8",
    );
    expect(panelSrc).not.toContain("leaderboardTitle");
    expect(panelSrc).not.toContain("viewLeaderboard");
    expect(panelSrc).toContain("rankedMembers");
    expect(panelSrc).toContain("topLevel");
    expect(leaderboardSrc).toContain("tabText");
    expect(leaderboardSrc).toContain("tabVoice");
    expect(leaderboardSrc).toContain("tabNetUpvotes");
    expect(storeSrc).toContain("Promise.all");
    expect(storeSrc).toContain("/leveling/leaderboard");
  });
});

describe("kick capacity copy", () => {
  it("gates Kick on total remaining including disabled", () => {
    const modalSrc = readFileSync(
      resolve(
        __dirname,
        "../components/content-notifications/account-editor-modal.tsx",
      ),
      "utf8",
    );
    expect(modalSrc).toContain("total_remaining");
    expect(modalSrc).toContain("kickDisabledCount");
    expect(modalSrc).toContain("disabledDoNotCount");
  });
});
