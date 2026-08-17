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
    expect(en.campaignHistoryPage.metricArchived).toBe("Archived Campaigns");
    expect(en.contentNotifications.historyModalTitle).toBe("History");
    expect(en.contentNotifications.historyPageTitle).toBe("Delivery History");
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
    expect(tr.sidebar.rssFeeds).toBe("RSS Akışları");
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
