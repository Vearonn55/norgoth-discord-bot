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
  /**
   * Stretches (>1) or compresses (<1) the level-up XP curve. Levels are always
   * derived live from stored XP, so changing this never rewrites anyone's XP.
   */
  level_threshold_scale: number;
  reward_roles: RewardRole[];
  /**
   * Base voice XP granted per minute of eligible voice participation (before
   * the global multiplier). A value of 0 disables voice XP entirely — there is
   * no separate enable flag; the numeric value is the source of truth.
   */
  voice_xp_per_minute: number;
};

export type LeaderboardEntry = {
  rank: number;
  user_id: string;
  name: string;
  username?: string | null;
  avatar_url?: string | null;
  xp: number;
  total_xp?: number;
  level: number;
  net_upvotes?: number;
  upvote_total?: number;
  downvote_total?: number;
  post_count?: number;
};

export type LeaderboardMetric = "text" | "voice" | "net_upvotes";

export const XP_PER_MESSAGE_MIN = 1;
export const XP_PER_MESSAGE_MAX = 100;
export const XP_MULTIPLIER_MIN = 0.1;
export const XP_MULTIPLIER_MAX = 5.0;
// 0 is the explicit "voice XP disabled" state; there is no separate toggle.
export const VOICE_XP_PER_MINUTE_MIN = 0;
export const VOICE_XP_PER_MINUTE_MAX = 100;
export const LEVEL_THRESHOLD_SCALE_MIN = 0.5;
export const LEVEL_THRESHOLD_SCALE_MAX = 2.0;
export const DEFAULT_LEVEL_THRESHOLD_SCALE = 1.0;

/** Clamp the curve scale into the supported range (fail-safe to default). */
export function clampThresholdScale(scale: number): number {
  if (!Number.isFinite(scale)) return DEFAULT_LEVEL_THRESHOLD_SCALE;
  return Math.max(
    LEVEL_THRESHOLD_SCALE_MIN,
    Math.min(LEVEL_THRESHOLD_SCALE_MAX, scale)
  );
}

/**
 * Total XP required to reach ``level`` under the given curve scale. Mirrors the
 * API/bot ``xp_for_level`` so the dashboard preview matches runtime exactly.
 */
export function xpForLevel(
  level: number,
  scale: number = DEFAULT_LEVEL_THRESHOLD_SCALE
): number {
  let total = 0;
  for (let step = 0; step < level; step++) {
    total += 5 * step * step + 50 * step + 100;
  }
  return Math.round(total * clampThresholdScale(scale));
}

const DEFAULT_LEVEL_UP_MESSAGE = "🎉 {user} reached level **{level}**!";

export const DEFAULT_LEVELING_CONFIG: LevelingConfig = {
  announce_mode: "current",
  announce_channel_id: null,
  xp_per_message: 15,
  xp_multiplier: 1.0,
  level_threshold_scale: DEFAULT_LEVEL_THRESHOLD_SCALE,
  level_up_message: DEFAULT_LEVEL_UP_MESSAGE,
  level_up_embed: {
    title: "Level up!",
    description: DEFAULT_LEVEL_UP_MESSAGE,
    color: "#5865f2",
    footer: "{server}",
    fields: [],
  },
  reward_roles: [],
  voice_xp_per_minute: 0,
};

export type LevelingCard = "xp" | "announce" | "rewards";

export const LEVELING_CARD_KEYS: Record<
  LevelingCard,
  readonly (keyof LevelingConfig)[]
> = {
  xp: [
    "xp_per_message",
    "voice_xp_per_minute",
    "xp_multiplier",
    "level_threshold_scale",
  ],
  announce: [
    "announce_mode",
    "announce_channel_id",
    "level_up_message",
    "level_up_embed",
  ],
  rewards: ["reward_roles"],
};

export function pickLevelingCard(
  config: LevelingConfig,
  card: LevelingCard
): Partial<LevelingConfig> {
  const picked: Partial<LevelingConfig> = {};
  for (const key of LEVELING_CARD_KEYS[card]) {
    (picked as Record<string, unknown>)[key] = config[key];
  }
  return picked;
}

export function levelingCardDirty(
  draft: LevelingConfig,
  server: LevelingConfig,
  card: LevelingCard
): boolean {
  return (
    JSON.stringify(pickLevelingCard(draft, card)) !==
    JSON.stringify(pickLevelingCard(server, card))
  );
}

/**
 * Consolidates legacy configs into the embed-only model: the level-up message
 * is the single source of truth for the embed description. If a legacy config
 * stored a separate embed description but no message body, adopt it as the
 * message; otherwise the message body wins.
 */
function normalizeLevelingConfig(
  config: LevelingConfig & { voice_xp_enabled?: boolean }
): LevelingConfig {
  const message =
    config.level_up_message?.trim() ||
    config.level_up_embed?.description?.trim() ||
    DEFAULT_LEVEL_UP_MESSAGE;
  // Legacy migration: older configs gated voice XP with a boolean. When that
  // flag was off, coerce the per-minute value to 0 (the new disabled state);
  // when on, keep the stored number. The boolean is then dropped entirely.
  const { voice_xp_enabled, ...rest } = config;
  const voicePerMinute =
    voice_xp_enabled === false ? 0 : Math.max(0, rest.voice_xp_per_minute ?? 0);
  return {
    ...rest,
    voice_xp_per_minute: voicePerMinute,
    level_up_message: message,
    level_up_embed: {
      ...rest.level_up_embed,
      description: message,
    },
  };
}

type LevelingState = {
  config: LevelingConfig;
  serverConfig: LevelingConfig;
  leaderboard: LeaderboardEntry[];
  leaderboardMetric: LeaderboardMetric;
  leaderboardLoading: boolean;
  saving: boolean;
  savingCard: LevelingCard | null;
  lastSavedCard: LevelingCard | null;
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
  setLeaderboardMetric: (metric: LeaderboardMetric) => void;
  setNewRewardLevel: (level: number) => void;
  setNewRewardRoleId: (roleId: string) => void;
  setFeedback: (feedback: string | null, isError?: boolean) => void;
  load: (guildId: string) => Promise<void>;
  loadLeaderboard: (
    guildId: string,
    metric?: LeaderboardMetric
  ) => Promise<void>;
  save: (guildId: string) => Promise<void>;
  saveCard: (guildId: string, card: LevelingCard) => Promise<void>;
  addReward: () => void;
};

export const useLevelingStore = create<LevelingState>((set, get) => ({
  config: DEFAULT_LEVELING_CONFIG,
  serverConfig: DEFAULT_LEVELING_CONFIG,
  leaderboard: [],
  leaderboardMetric: "text",
  leaderboardLoading: false,
  saving: false,
  savingCard: null,
  lastSavedCard: null,
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
  setLeaderboardMetric: (metric) =>
    set({ leaderboardMetric: metric, leaderboardPage: 1 }),
  setNewRewardLevel: (level) => set({ newRewardLevel: level }),
  setNewRewardRoleId: (roleId) => set({ newRewardRoleId: roleId }),
  setFeedback: (feedback, isError = false) =>
    set({ feedback, feedbackIsError: isError }),
  loadLeaderboard: async (guildId, metric) => {
    const activeMetric = metric ?? get().leaderboardMetric;
    if (get().leaderboardLoading && get().leaderboardMetric === activeMetric) {
      return;
    }
    const requestMetric = activeMetric;
    set({
      leaderboardLoading: true,
      leaderboardMetric: activeMetric,
      feedback: null,
      feedbackIsError: false,
    });
    try {
      const leaderboardResponse = await fetch(
        apiUrl(
          `/guilds/${guildId}/leveling/leaderboard?metric=${activeMetric}`
        ),
        { cache: "no-store" }
      );
      if (get().leaderboardMetric !== requestMetric) {
        return;
      }
      if (leaderboardResponse.ok) {
        set({
          leaderboard: (await leaderboardResponse.json()) as LeaderboardEntry[],
          leaderboardLoading: false,
          feedback: null,
          feedbackIsError: false,
        });
      } else {
        set({
          leaderboard: [],
          leaderboardLoading: false,
          feedback: `Could not load the ${
            activeMetric === "voice"
              ? "Voice XP"
              : activeMetric === "net_upvotes"
                ? "Top Upvote"
                : "Text XP"
          } leaderboard (${leaderboardResponse.status}).`,
          feedbackIsError: true,
        });
      }
    } catch {
      if (get().leaderboardMetric !== requestMetric) {
        return;
      }
      set({
        leaderboard: [],
        leaderboardLoading: false,
        feedback: "Could not reach the Norgoth API.",
        feedbackIsError: true,
      });
    }
  },
  load: async (guildId) => {
    try {
      const metric = get().leaderboardMetric;
      const [configResponse, leaderboardResponse] = await Promise.all([
        fetch(apiUrl(`/guilds/${guildId}/leveling/config`), {
          cache: "no-store",
        }),
        fetch(
          apiUrl(`/guilds/${guildId}/leveling/leaderboard?metric=${metric}`),
          {
            cache: "no-store",
          }
        ),
      ]);

      if (configResponse.ok) {
        const stored = (await configResponse.json()) as LevelingConfig;
        const normalized = normalizeLevelingConfig({
          ...DEFAULT_LEVELING_CONFIG,
          ...stored,
        });
        set({
          config: normalized,
          serverConfig: normalized,
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
    await get().saveCard(guildId, "rewards");
  },
  saveCard: async (guildId, card) => {
    set({
      saving: true,
      savingCard: card,
      lastSavedCard: card,
      feedback: null,
    });
    try {
      let snapshot = get().serverConfig;
      const latestResponse = await fetch(
        apiUrl(`/guilds/${guildId}/leveling/config`),
        { cache: "no-store" }
      );
      if (latestResponse.ok) {
        snapshot = normalizeLevelingConfig({
          ...DEFAULT_LEVELING_CONFIG,
          ...((await latestResponse.json()) as LevelingConfig),
        });
      }
      const payload = normalizeLevelingConfig({
        ...snapshot,
        ...pickLevelingCard(get().config, card),
      });
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/leveling/config`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );

      if (response.ok) {
        const saved = normalizeLevelingConfig({
          ...DEFAULT_LEVELING_CONFIG,
          ...((await response.json()) as LevelingConfig),
        });
        set({
          serverConfig: saved,
          config: {
            ...get().config,
            ...pickLevelingCard(saved, card),
          },
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
      set({ saving: false, savingCard: null });
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
