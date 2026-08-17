"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";
import { readApiError } from "@/lib/api-error";

export type AutomodAction = "delete" | "warn" | "timeout";

export type ModerationScope = {
  text: boolean;
  threads: boolean;
  voice_text: boolean;
};

export type AutomodConfig = {
  enabled: boolean;
  moderation_scope: ModerationScope;
  words_enabled: boolean;
  prohibited_words: string[];
  word_action: AutomodAction;
  spam_enabled: boolean;
  spam_max_messages: number;
  spam_interval_seconds: number;
  spam_action: AutomodAction;
  duplicate_enabled: boolean;
  duplicate_threshold: number;
  block_invites: boolean;
  invite_action: AutomodAction;
  mass_mention_enabled: boolean;
  mass_mention_threshold: number;
  mass_mention_action: AutomodAction;
  timeout_minutes: number;
  exempt_manage_messages: boolean;
  exempt_channel_ids: string[];
  exempt_role_ids: string[];
  image_only_enabled: boolean;
  image_only_channel_ids: string[];
  image_only_action: AutomodAction;
  link_only_enabled: boolean;
  link_only_channel_ids: string[];
  link_only_action: AutomodAction;
};

export const DEFAULT_AUTOMOD_CONFIG: AutomodConfig = {
  enabled: false,
  moderation_scope: { text: true, threads: true, voice_text: true },
  words_enabled: true,
  prohibited_words: [],
  word_action: "delete",
  spam_enabled: true,
  spam_max_messages: 6,
  spam_interval_seconds: 8,
  spam_action: "timeout",
  duplicate_enabled: true,
  duplicate_threshold: 3,
  block_invites: false,
  invite_action: "delete",
  mass_mention_enabled: true,
  mass_mention_threshold: 6,
  mass_mention_action: "delete",
  timeout_minutes: 10,
  exempt_manage_messages: true,
  exempt_channel_ids: [],
  exempt_role_ids: [],
  image_only_enabled: false,
  image_only_channel_ids: [],
  image_only_action: "delete",
  link_only_enabled: false,
  link_only_channel_ids: [],
  link_only_action: "delete",
};

type AutomodState = {
  config: AutomodConfig;
  savedSnapshot: string;
  wordInput: string;
  wordSearch: string;
  wordPage: number;
  saving: boolean;
  saveError: string | null;
  saveErrorCode: string | null;
  savedAt: string | null;
  setConfig: (
    config: AutomodConfig | ((current: AutomodConfig) => AutomodConfig)
  ) => void;
  setWordInput: (value: string) => void;
  setWordSearch: (value: string) => void;
  setWordPage: (page: number) => void;
  load: (guildId: string) => Promise<void>;
  save: (guildId: string) => Promise<void>;
  addWord: () => void;
  removeWord: (word: string) => void;
};

export const useAutomodStore = create<AutomodState>((set, get) => ({
  config: DEFAULT_AUTOMOD_CONFIG,
  savedSnapshot: JSON.stringify(DEFAULT_AUTOMOD_CONFIG),
  wordInput: "",
  wordSearch: "",
  wordPage: 1,
  saving: false,
  saveError: null,
  saveErrorCode: null,
  savedAt: null,
  setConfig: (config) =>
    set((state) => ({
      config: typeof config === "function" ? config(state.config) : config,
    })),
  setWordInput: (value) => set({ wordInput: value }),
  setWordSearch: (value) => set({ wordSearch: value, wordPage: 1 }),
  setWordPage: (page) => set({ wordPage: page }),
  load: async (guildId) => {
    try {
      const response = await fetch(apiUrl(`/guilds/${guildId}/automod`), {
        cache: "no-store",
      });

      if (response.ok) {
        const stored = (await response.json()) as AutomodConfig;
        const next = { ...DEFAULT_AUTOMOD_CONFIG, ...stored };
        set({
          config: next,
          savedSnapshot: JSON.stringify(next),
        });
      }
    } catch {
      set({
        saveError: "Could not load the automod configuration.",
        saveErrorCode: "http_error",
      });
    }
  },
  save: async (guildId) => {
    set({ saving: true, saveError: null, saveErrorCode: null });
    try {
      const { config } = get();
      const response = await fetch(apiUrl(`/guilds/${guildId}/automod`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        const err = await readApiError(response);
        set({ saveError: err.message, saveErrorCode: err.code });
        return;
      }

      set({
        savedSnapshot: JSON.stringify(config),
        savedAt: new Date().toLocaleTimeString(),
        saveError: null,
        saveErrorCode: null,
      });
    } catch {
      set({
        saveError: "Save failed: could not reach the API.",
        saveErrorCode: "http_error",
      });
    } finally {
      set({ saving: false });
    }
  },
  addWord: () => {
    const cleaned = get().wordInput.trim().toLowerCase();
    if (!cleaned) return;

    set((state) => ({
      config: {
        ...state.config,
        prohibited_words: state.config.prohibited_words.includes(cleaned)
          ? state.config.prohibited_words
          : [...state.config.prohibited_words, cleaned],
      },
      wordInput: "",
      wordPage: 1,
    }));
  },
  removeWord: (word) =>
    set((state) => ({
      config: {
        ...state.config,
        prohibited_words: state.config.prohibited_words.filter((w) => w !== word),
      },
    })),
}));
