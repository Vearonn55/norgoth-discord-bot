export type CampaignDeliveryTarget = "channel" | "dm";
export type CampaignMessageType = "text" | "embed";
export type CampaignLaunchMode = "now" | "scheduled";

export type CampaignPlatform = "discord";

export type CampaignWizardState = {
  basics: {
    name: string;
    description: string;
  };

  audience: {
    deliveryTarget: CampaignDeliveryTarget;
    channelId: string;
    includeRoleIds: string[];
    excludeRoleIds: string[];
  };

  message: {
    messageType: CampaignMessageType;
    subject: string;
    body: string;
    embedColor: string;
    embedThumbnailUrl: string;
    embedImageUrl: string;
  };

  launch: {
    launchMode: CampaignLaunchMode;
    scheduledDate: string;
    scheduledTime: string;
  };
};

export const defaultCampaignWizardState: CampaignWizardState = {
  basics: {
    name: "",
    description: "",
  },

  audience: {
    deliveryTarget: "channel",
    channelId: "",
    includeRoleIds: [],
    excludeRoleIds: [],
  },

  message: {
    messageType: "embed",
    subject: "",
    body: "",
    embedColor: "#5865f2",
    embedThumbnailUrl: "",
    embedImageUrl: "",
  },

  launch: {
    launchMode: "now",
    scheduledDate: "",
    scheduledTime: "",
  },
};
