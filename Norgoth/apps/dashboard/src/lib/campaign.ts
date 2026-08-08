import type { CampaignWizardState } from "@/types/campaign";

type BuildOptions = {
  guildId: string | null;
  audienceCount: number;
  launchAt: string | null;
  riskLevel: "low" | "medium" | "high";
};

export function buildCampaignPayload(
  state: CampaignWizardState,
  options: BuildOptions,
) {
  const isDM = state.audience.deliveryTarget === "dm";

  return {
    title: state.basics.name.trim(),
    name: state.basics.name.trim(),
    message: {
      title: state.message.subject.trim() || state.basics.name.trim(),
      body: state.message.body.trim(),
      format: state.message.messageType,
      color: state.message.embedColor || null,
      thumbnail_url: state.message.embedThumbnailUrl || null,
      image_url: state.message.embedImageUrl || null,
    },
    body: state.message.body.trim(),
    type: isDM ? "dm-campaign" : "channel-broadcast",
    audience: {
      segment: isDM ? "dm-members" : "channel-broadcast",
      count: options.audienceCount,
    },
    audience_count: options.audienceCount,
    status: options.launchAt ? "scheduled" : "queued",
    launch_at: options.launchAt,
    risk_level: options.riskLevel,
    delivery_target: state.audience.deliveryTarget,
    guild_id: options.guildId,
    discord_channel_id: isDM ? null : state.audience.channelId || null,
    dm_include_role_ids: isDM ? state.audience.includeRoleIds : [],
    dm_exclude_role_ids: isDM ? state.audience.excludeRoleIds : [],
    tags: [state.audience.deliveryTarget, state.message.messageType],
    locales: ["en"],
  };
}
