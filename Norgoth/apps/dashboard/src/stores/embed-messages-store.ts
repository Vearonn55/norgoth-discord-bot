"use client";

import { create } from "zustand";
import { apiUrl, readError } from "@/lib/api";
import type { DiscordEmbedPayload } from "@/lib/discord/message-payload";

export type EmbedDeliveryStatus =
  | "synced"
  | "message_missing"
  | "channel_missing"
  | "permission_missing"
  | "webhook_missing"
  | "pending"
  | "error";

export type EmbedMessageDelivery = {
  id: string;
  channel_id: string;
  discord_message_id: string | null;
  delivery_type: string;
  status: EmbedDeliveryStatus;
  error: string | null;
  deployed_version: number | null;
  stale: boolean;
  last_synced_at: string | null;
  created_at: string | null;
};

export type EmbedMessage = {
  id: string;
  guild_id: string;
  name: string;
  description: string;
  content: string;
  embed_json: DiscordEmbedPayload | null;
  target_channel_ids: string[];
  version: number;
  has_published: boolean;
  synced_count: number;
  target_count: number;
  needs_resync: boolean;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
  deliveries: EmbedMessageDelivery[];
};

export type EmbedMessageInput = {
  name: string;
  description: string;
  content: string;
  embed_json: DiscordEmbedPayload | null;
  target_channel_ids: string[];
};

type EmbedMessagesState = {
  messages: EmbedMessage[];
  loading: boolean;
  error: string | null;
  load: (guildId: string) => Promise<void>;
  get: (guildId: string, id: string) => Promise<EmbedMessage | null>;
  create: (
    guildId: string,
    input: EmbedMessageInput
  ) => Promise<EmbedMessage | null>;
  update: (
    guildId: string,
    id: string,
    input: EmbedMessageInput
  ) => Promise<EmbedMessage | null>;
  remove: (
    guildId: string,
    id: string,
    deleteDiscordMessages?: boolean
  ) => Promise<boolean>;
  send: (
    guildId: string,
    id: string,
    channelId: string
  ) => Promise<EmbedMessage | null>;
  sync: (guildId: string, id: string) => Promise<EmbedMessage | null>;
  publish: (guildId: string, id: string) => Promise<EmbedMessage | null>;
  resync: (guildId: string, id: string) => Promise<EmbedMessage | null>;
  reconcile: (guildId: string, id: string) => Promise<EmbedMessage | null>;
};

function base(guildId: string): string {
  return `/guilds/${guildId}/embed-messages`;
}

export const useEmbedMessagesStore = create<EmbedMessagesState>((set) => ({
  messages: [],
  loading: false,
  error: null,

  load: async (guildId) => {
    set({ loading: true, error: null });
    try {
      const response = await fetch(apiUrl(base(guildId)), {
        cache: "no-store",
      });
      if (!response.ok) {
        set({ messages: [], loading: false, error: "Failed to load." });
        return;
      }
      const data = (await response.json()) as EmbedMessage[];
      set({ messages: data, loading: false });
    } catch {
      set({ messages: [], loading: false, error: "Network error." });
    }
  },

  get: async (guildId, id) => {
    try {
      const response = await fetch(apiUrl(`${base(guildId)}/${id}`), {
        cache: "no-store",
      });
      if (!response.ok) return null;
      return (await response.json()) as EmbedMessage;
    } catch {
      return null;
    }
  },

  create: async (guildId, input) => {
    set({ error: null });
    try {
      const response = await fetch(apiUrl(base(guildId)), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      });
      if (!response.ok) {
        set({ error: await readError(response) });
        return null;
      }
      const created = (await response.json()) as EmbedMessage;
      set((state) => ({ messages: [created, ...state.messages] }));
      return created;
    } catch {
      set({ error: "Could not reach the Norgoth API." });
      return null;
    }
  },

  update: async (guildId, id, input) => {
    set({ error: null });
    try {
      const response = await fetch(apiUrl(`${base(guildId)}/${id}`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      });
      if (!response.ok) {
        set({ error: await readError(response) });
        return null;
      }
      const updated = (await response.json()) as EmbedMessage;
      set((state) => ({
        messages: state.messages.map((m) => (m.id === id ? updated : m)),
      }));
      return updated;
    } catch {
      set({ error: "Could not reach the Norgoth API." });
      return null;
    }
  },

  remove: async (guildId, id, deleteDiscordMessages = false) => {
    const response = await fetch(apiUrl(`${base(guildId)}/${id}`), {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ delete_discord_messages: deleteDiscordMessages }),
    });
    if (!response.ok) return false;
    set((state) => ({
      messages: state.messages.filter((m) => m.id !== id),
    }));
    return true;
  },

  send: async (guildId, id, channelId) => {
    const response = await fetch(apiUrl(`${base(guildId)}/${id}/send`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel_id: channelId }),
    });
    if (!response.ok) return null;
    const updated = (await response.json()) as EmbedMessage;
    set((state) => ({
      messages: state.messages.map((m) => (m.id === id ? updated : m)),
    }));
    return updated;
  },

  sync: async (guildId, id) => {
    const response = await fetch(apiUrl(`${base(guildId)}/${id}/sync`), {
      method: "POST",
    });
    if (!response.ok) return null;
    const updated = (await response.json()) as EmbedMessage;
    set((state) => ({
      messages: state.messages.map((m) => (m.id === id ? updated : m)),
    }));
    return updated;
  },

  publish: async (guildId, id) => {
    set({ error: null });
    const response = await fetch(apiUrl(`${base(guildId)}/${id}/publish`), {
      method: "POST",
    });
    if (!response.ok) {
      set({ error: await readError(response) });
      return null;
    }
    const updated = (await response.json()) as EmbedMessage;
    set((state) => ({
      messages: state.messages.map((m) => (m.id === id ? updated : m)),
    }));
    return updated;
  },

  resync: async (guildId, id) => {
    set({ error: null });
    const response = await fetch(apiUrl(`${base(guildId)}/${id}/resync`), {
      method: "POST",
    });
    if (!response.ok) {
      set({ error: await readError(response) });
      return null;
    }
    const updated = (await response.json()) as EmbedMessage;
    set((state) => ({
      messages: state.messages.map((m) => (m.id === id ? updated : m)),
    }));
    return updated;
  },

  reconcile: async (guildId, id) => {
    set({ error: null });
    const response = await fetch(apiUrl(`${base(guildId)}/${id}/reconcile`), {
      method: "POST",
    });
    if (!response.ok) {
      set({ error: await readError(response) });
      return null;
    }
    const updated = (await response.json()) as EmbedMessage;
    set((state) => ({
      messages: state.messages.map((m) => (m.id === id ? updated : m)),
    }));
    return updated;
  },
}));
