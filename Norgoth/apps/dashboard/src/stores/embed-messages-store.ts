"use client";

import { create } from "zustand";
import { apiUrl, readError } from "@/lib/api";
import { readApiError } from "@/lib/api-error";
import type { DiscordEmbedPayload } from "@/lib/discord/message-payload";

export type EmbedDeliveryStatus =
  | "synced"
  | "message_missing"
  | "channel_missing"
  | "permission_missing"
  | "webhook_missing"
  | "pending"
  | "error";

/** Per-deployment reconciliation state derived by the backend. */
export type EmbedDeliveryState =
  | "pending"
  | "synced"
  | "out_of_date"
  | "missing"
  | "needs_feature_repair"
  | "error";

export type EmbedMessageDelivery = {
  id: string;
  channel_id: string;
  discord_message_id: string | null;
  discord_message_ids?: string[] | null;
  delivery_type: string;
  status: EmbedDeliveryStatus;
  state: EmbedDeliveryState;
  owner_feature: string;
  error: string | null;
  deployed_version: number | null;
  stale: boolean;
  last_synced_at: string | null;
  created_at: string | null;
  published_at: string | null;
};

export type EmbedSyncStatus =
  | "draft_only"
  | "pending"
  | "synced"
  | "out_of_date"
  | "missing"
  | "needs_feature_repair"
  | "error";

export type EmbedMessage = {
  id: string;
  guild_id: string;
  name: string;
  description: string;
  content: string;
  embed_json: DiscordEmbedPayload | null;
  version: number;
  has_published: boolean;
  deployment_count: number;
  synced_count: number;
  current_count: number;
  needs_resync: boolean;
  sync_status: EmbedSyncStatus;
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
};

type EmbedMessagesState = {
  messages: EmbedMessage[];
  loading: boolean;
  error: string | null;
  errorCode: string | null;
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
    options?: { deleteDiscordMessages?: boolean; force?: boolean }
  ) => Promise<boolean>;
  /** Post the draft to a channel now, creating a library-owned deployment. */
  deploy: (
    guildId: string,
    id: string,
    channelId: string
  ) => Promise<EmbedMessage | null>;
  /** Alias of {@link deploy} kept for feature hosts (e.g. role menus). */
  send: (
    guildId: string,
    id: string,
    channelId: string
  ) => Promise<EmbedMessage | null>;
  resync: (guildId: string, id: string) => Promise<EmbedMessage | null>;
  resyncDelivery: (
    guildId: string,
    id: string,
    deliveryId: string
  ) => Promise<EmbedMessage | null>;
  reconcile: (guildId: string, id: string) => Promise<EmbedMessage | null>;
};

function base(guildId: string): string {
  return `/guilds/${guildId}/embed-messages`;
}

function deployIdempotencyStorageKey(draftId: string, channelId: string): string {
  return `norgoth:embed-deploy:${draftId}:${channelId}`;
}

function readDeployIdempotencyKey(draftId: string, channelId: string): string {
  const storageKey = deployIdempotencyStorageKey(draftId, channelId);
  try {
    if (typeof sessionStorage !== "undefined") {
      const existing = sessionStorage.getItem(storageKey);
      if (existing) return existing;
      const next = crypto.randomUUID();
      sessionStorage.setItem(storageKey, next);
      return next;
    }
  } catch {
    /* private mode / non-browser */
  }
  return crypto.randomUUID();
}

function clearDeployIdempotencyKey(draftId: string, channelId: string): void {
  try {
    if (typeof sessionStorage !== "undefined") {
      sessionStorage.removeItem(deployIdempotencyStorageKey(draftId, channelId));
    }
  } catch {
    /* ignore */
  }
}

export const useEmbedMessagesStore = create<EmbedMessagesState>((set) => ({
  messages: [],
  loading: false,
  error: null,
  errorCode: null,

  load: async (guildId) => {
    set({ loading: true, error: null, errorCode: null });
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
    set({ error: null, errorCode: null });
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
    set({ error: null, errorCode: null });
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

  remove: async (guildId, id, options = {}) => {
    set({ error: null, errorCode: null });
    const response = await fetch(apiUrl(`${base(guildId)}/${id}`), {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        delete_discord_messages: options.deleteDiscordMessages ?? false,
        force: options.force ?? false,
      }),
    });
    if (!response.ok) {
      set({ error: await readError(response) });
      return false;
    }
    set((state) => ({
      messages: state.messages.filter((m) => m.id !== id),
    }));
    return true;
  },

  deploy: async (guildId, id, channelId) => {
    set({ error: null, errorCode: null });
    const idempotencyKey = readDeployIdempotencyKey(id, channelId);
    const response = await fetch(apiUrl(`${base(guildId)}/${id}/send`), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify({ channel_id: channelId }),
    });
    if (!response.ok) {
      const apiError = await readApiError(response);
      set({ error: apiError.message, errorCode: apiError.code });
      return null;
    }
    clearDeployIdempotencyKey(id, channelId);
    const updated = (await response.json()) as EmbedMessage;
    set((state) => ({
      messages: state.messages.map((m) => (m.id === id ? updated : m)),
    }));
    return updated;
  },

  send: async (guildId, id, channelId) => {
    set({ error: null, errorCode: null });
    const idempotencyKey = readDeployIdempotencyKey(id, channelId);
    const response = await fetch(apiUrl(`${base(guildId)}/${id}/send`), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify({ channel_id: channelId }),
    });
    if (!response.ok) {
      const apiError = await readApiError(response);
      set({ error: apiError.message, errorCode: apiError.code });
      return null;
    }
    clearDeployIdempotencyKey(id, channelId);
    const updated = (await response.json()) as EmbedMessage;
    set((state) => ({
      messages: state.messages.map((m) => (m.id === id ? updated : m)),
      error: null,
      errorCode: null,
    }));
    return updated;
  },

  resync: async (guildId, id) => {
    set({ error: null, errorCode: null });
    const response = await fetch(apiUrl(`${base(guildId)}/${id}/resync`), {
      method: "POST",
    });
    if (!response.ok) {
      const apiError = await readApiError(response);
      set({ error: apiError.message, errorCode: apiError.code });
      return null;
    }
    const updated = (await response.json()) as EmbedMessage;
    set((state) => ({
      messages: state.messages.map((m) => (m.id === id ? updated : m)),
    }));
    return updated;
  },

  resyncDelivery: async (guildId, id, deliveryId) => {
    set({ error: null, errorCode: null });
    const response = await fetch(
      apiUrl(`${base(guildId)}/${id}/deliveries/${deliveryId}/resync`),
      { method: "POST" }
    );
    if (!response.ok) {
      const apiError = await readApiError(response);
      set({ error: apiError.message, errorCode: apiError.code });
      return null;
    }
    const updated = (await response.json()) as EmbedMessage;
    set((state) => ({
      messages: state.messages.map((m) => (m.id === id ? updated : m)),
    }));
    return updated;
  },

  reconcile: async (guildId, id) => {
    set({ error: null, errorCode: null });
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
