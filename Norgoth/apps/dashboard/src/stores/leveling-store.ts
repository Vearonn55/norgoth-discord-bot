"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";
import type { DiscordEmbedPayload } from "@/lib/discord/message-payload";

export type RewardRole = {
  level: number;
  role_id: string;
};

export type LevelingConfig = {
  announce_mode: "current" | "channel" | "off";
  announce_channel_id: string | null;
  xp_per_message: number;
  xp_multiplier: number;
  /**
   * Level-up body composed in TinyMCE (Discord markdown). This is the single
   * source of truth for the embed description — level-up messages are always
   * sent as embeds.
   */
  level_up_message: string;
  level_up_embed: DiscordEmbedPayload;
  reward_roles: RewardRole[];
};

export type LeaderboardEntry = {
  rank: number;
  user_id: string;
  name: string;
  xp: number;
  level: number;
};

export const XP_PER_MESSAGE_MIN = 1;
export const XP_PER_MESSAGE_MAX = 100;
export const XP_MULTIPLIER_MIN = 0.1;
export const XP_MULTIPLIER_MAX = 5.0;

const DEFAULT_LEVEL_UP_MESSAGE = "🎉 {user} reached level **{level}**!";

export const DEFAULT_LEVELING_CONFIG: LevelingConfig = {
  announce_mode: "current",
  announce_channel_id: null,
  xp_per_message: 15,
  xp_multiplier: 1.0,
  level_up_message: DEFAULT_LEVEL_UP_MESSAGE,
  level_up_embed: {
    title: "Level up!",
    description: DEFAULT_LEVEL_UP_MESSAGE,
    color: "#5865f2",
    footer: "{server}",
    fields: [],
  },
  reward_roles: [],
};

/**
 * Consolidates legacy configs into the embed-only model: the level-up message
 * is the single source of truth for the embed description. If a legacy config
 * stored a separate embed description but no message body, adopt it as the
 * message; otherwise the message body wins.
 */
function normalizeLevelingConfig(config: LevelingConfig): LevelingConfig {
  const message =
    config.level_up_message?.trim() ||
    config.level_up_embed?.description?.trim() ||
    DEFAULT_LEVEL_UP_MESSAGE;
  return {
    ...config,
    level_up_message: message,
    level_up_embed: {
      ...config.level_up_embed,
      description: message,
    },
  };
}

type LevelingState = {
  config: LevelingConfig;
  leaderboard: LeaderboardEntry[];
  saving: boolean;
  feedback: string | null;
  feedbackIsError: boolean;
  rewardSearch: string;
  rewardPage: number;
  leaderboardSearch: string;
  leaderboardPage: number;
  newRewardLevel: number;
  newRewardRoleId: string;
  setConfig: (
    config: LevelingConfig | ((current: LevelingConfig) => LevelingConfig)
  ) => void;
  /** Updates the level-up body and keeps the embed description in sync. */
  setLevelUpMessage: (message: string) => void;
  setRewardSearch: (value: string) => void;
  setRewardPage: (page: number) => void;
  setLeaderboardSearch: (value: string) => void;
  setLeaderboardPage: (page: number) => void;
  setNewRewardLevel: (level: number) => void;
  setNewRewardRoleId: (roleId: string) => void;
  setFeedback: (feedback: string | null, isError?: boolean) => void;
  load: (guildId: string) => Promise<void>;
  save: (guildId: string) => Promise<void>;
  addReward: () => void;
};

export const useLevelingStore = create<LevelingState>((set, get) => ({
  config: DEFAULT_LEVELING_CONFIG,
  leaderboard: [],
  saving: false,
  feedback: null,
  feedbackIsError: false,
  rewardSearch: "",
  rewardPage: 1,
  leaderboardSearch: "",
  leaderboardPage: 1,
  newRewardLevel: 5,
  newRewardRoleId: "",
  setConfig: (config) =>
    set((state) => ({
      config: typeof config === "function" ? config(state.config) : config,
    })),
  setLevelUpMessage: (message) =>
    set((state) => ({
      config: {
        ...state.config,
        level_up_message: message,
        level_up_embed: {
          ...state.config.level_up_embed,
          description: message,
        },
      },
    })),
  setRewardSearch: (value) => set({ rewardSearch: value, rewardPage: 1 }),
  setRewardPage: (page) => set({ rewardPage: page }),
  setLeaderboardSearch: (value) =>
    set({ leaderboardSearch: value, leaderboardPage: 1 }),
  setLeaderboardPage: (page) => set({ leaderboardPage: page }),
  setNewRewardLevel: (level) => set({ newRewardLevel: level }),
  setNewRewardRoleId: (roleId) => set({ newRewardRoleId: roleId }),
  setFeedback: (feedback, isError = false) =>
    set({ feedback, feedbackIsError: isError }),
  load: async (guildId) => {
    try {
      const [configResponse, leaderboardResponse] = await Promise.all([
        fetch(apiUrl(`/guilds/${guildId}/leveling/config`), {
          cache: "no-store",
        }),
        fetch(apiUrl(`/guilds/${guildId}/leveling/leaderboard`), {
          cache: "no-store",
        }),
      ]);

      if (configResponse.ok) {
        const stored = (await configResponse.json()) as LevelingConfig;
        set({
          config: normalizeLevelingConfig({
            ...DEFAULT_LEVELING_CONFIG,
            ...stored,
          }),
        });
      }

      if (leaderboardResponse.ok) {
        set({
          leaderboard: (await leaderboardResponse.json()) as LeaderboardEntry[],
        });
      }
    } catch {
      set({
        feedback: "Could not reach the Norgoth API.",
        feedbackIsError: true,
      });
    }
  },
  save: async (guildId) => {
    set({ saving: true, feedback: null });
    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/leveling/config`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(normalizeLevelingConfig(get().config)),
        }
      );

      if (response.ok) {
        set({
          feedback: `Settings saved at ${new Date().toLocaleTimeString()}.`,
          feedbackIsError: false,
        });
      } else {
        set({
          feedback: `Save failed: ${await response.text()}`,
          feedbackIsError: true,
        });
      }
    } catch {
      set({
        feedback: "Save failed: could not reach the API.",
        feedbackIsError: true,
      });
    } finally {
      set({ saving: false });
    }
  },
  addReward: () => {
    const { newRewardRoleId, newRewardLevel, config } = get();
    if (!newRewardRoleId) return;

    set({
      config: {
        ...config,
        reward_roles: [
          ...config.reward_roles.filter(
            (reward) => reward.level !== newRewardLevel
          ),
          { level: newRewardLevel, role_id: newRewardRoleId },
        ].sort((a, b) => a.level - b.level),
      },
    });
  },
}));
