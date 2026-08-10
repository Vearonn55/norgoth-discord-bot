"use client";

import { create } from "zustand";
import { apiUrl } from "@/lib/api";
import { createId } from "@/lib/id";

export type TicketsConfig = {
  category_id: string | null;
  log_channel_id: string | null;
  support_role_ids: string[];
  welcome_text: string;
};

export type TicketPanel = {
  id: string;
  name: string;
  channel_id: string | null;
  /** @deprecated Prefer embed_message_id / text_content. */
  title: string;
  /** @deprecated Prefer text_content; kept for legacy panels. */
  description: string;
  button_label: string;
  /** text = RichMessageEditor body; embed = Embed Library draft. */
  message_source: "text" | "embed";
  text_content: string;
  /** Central Embed Library draft used for the panel message visual. */
  embed_message_id: string | null;
  /** Discord category tickets from this panel are created under. */
  open_category_id: string | null;
  message_id: string | null;
  published_at: string | null;
  updated_at: string | null;
};

export function newTicketPanel(): TicketPanel {
  return {
    id: createId(),
    name: "Support panel",
    channel_id: null,
    title: "Need help?",
    description: "Click the button below to open a private support ticket.",
    button_label: "Open Ticket",
    message_source: "embed",
    text_content: "Click the button below to open a private support ticket.",
    embed_message_id: null,
    open_category_id: null,
    message_id: null,
    published_at: null,
    updated_at: null,
  };
}

export function normalizeTicketPanel(
  panel: Partial<TicketPanel> & { id?: string }
): TicketPanel {
  const base = { ...newTicketPanel(), ...panel };
  const source =
    panel.message_source === "text" || panel.message_source === "embed"
      ? panel.message_source
      : panel.embed_message_id
        ? "embed"
        : panel.text_content || panel.description || panel.title
          ? "text"
          : "embed";
  return {
    ...base,
    message_source: source,
    text_content:
      panel.text_content ??
      (source === "text"
        ? panel.description || panel.title || base.text_content
        : base.text_content),
    embed_message_id: panel.embed_message_id ?? null,
  };
}

export type TicketRecord = {
  id: string;
  number: number;
  channel_id: string;
  channel_name: string;
  opener_name: string;
  status: "open" | "closed";
  opened_at: string;
  closed_at: string | null;
  closed_by: string | null;
};

export const DEFAULT_TICKETS_CONFIG: TicketsConfig = {
  category_id: null,
  log_channel_id: null,
  support_role_ids: [],
  welcome_text:
    "Support will be with you shortly. Describe your issue here.",
};

type TicketsState = {
  config: TicketsConfig;
  tickets: TicketRecord[];
  panels: TicketPanel[];
  editingPanel: TicketPanel | null;
  panelsSaving: boolean;
  publishingPanelId: string | null;
  loading: boolean;
  saving: boolean;
  feedback: string | null;
  feedbackIsError: boolean;
  transcript: { ticketNumber: number; text: string } | null;
  setConfig: (config: TicketsConfig | ((current: TicketsConfig) => TicketsConfig)) => void;
  setFeedback: (feedback: string | null, isError?: boolean) => void;
  setTranscript: (transcript: { ticketNumber: number; text: string } | null) => void;
  setEditingPanel: (
    panel:
      | TicketPanel
      | null
      | ((current: TicketPanel | null) => TicketPanel | null)
  ) => void;
  load: (guildId: string) => Promise<void>;
  loadPanels: (guildId: string) => Promise<void>;
  save: (guildId: string) => Promise<void>;
  saveEditingPanel: (guildId: string) => Promise<boolean>;
  deletePanel: (guildId: string, panelId: string) => Promise<void>;
  publishPanelById: (guildId: string, panelId: string) => Promise<void>;
  viewTranscript: (guildId: string, ticket: TicketRecord) => Promise<void>;
};

export const useTicketsStore = create<TicketsState>((set, get) => ({
  config: DEFAULT_TICKETS_CONFIG,
  tickets: [],
  panels: [],
  editingPanel: null,
  panelsSaving: false,
  publishingPanelId: null,
  loading: false,
  saving: false,
  feedback: null,
  feedbackIsError: false,
  transcript: null,
  setConfig: (config) =>
    set((state) => ({
      config: typeof config === "function" ? config(state.config) : config,
    })),
  setFeedback: (feedback, isError = false) =>
    set({ feedback, feedbackIsError: isError }),
  setTranscript: (transcript) => set({ transcript }),
  setEditingPanel: (panel) =>
    set((state) => ({
      editingPanel:
        typeof panel === "function" ? panel(state.editingPanel) : panel,
    })),
  load: async (guildId) => {
    set({ loading: true });
    try {
      const [configResponse, ticketsResponse, panelsResponse] =
        await Promise.all([
          fetch(apiUrl(`/guilds/${guildId}/tickets/config`), {
            cache: "no-store",
          }),
          fetch(apiUrl(`/guilds/${guildId}/tickets`), {
            cache: "no-store",
          }),
          fetch(apiUrl(`/guilds/${guildId}/tickets/panels`), {
            cache: "no-store",
          }),
        ]);

      if (configResponse.ok) {
        const stored = (await configResponse.json()) as TicketsConfig;
        set({ config: { ...DEFAULT_TICKETS_CONFIG, ...stored } });
      }

      if (ticketsResponse.ok) {
        set({ tickets: (await ticketsResponse.json()) as TicketRecord[] });
      }

        if (panelsResponse.ok) {
        const body = (await panelsResponse.json()) as {
          panels: TicketPanel[];
        };
        set({
          panels: (body.panels ?? []).map((panel) =>
            normalizeTicketPanel(panel)
          ),
        });
      }
    } catch {
      set({
        feedback: "Could not reach the Norgoth API.",
        feedbackIsError: true,
      });
    } finally {
      set({ loading: false });
    }
  },
  loadPanels: async (guildId) => {
    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/tickets/panels`),
        { cache: "no-store" }
      );
      if (response.ok) {
        const body = (await response.json()) as { panels: TicketPanel[] };
        set({
          panels: (body.panels ?? []).map((panel) =>
            normalizeTicketPanel(panel)
          ),
        });
      }
    } catch {
      /* non-fatal: keep existing panels */
    }
  },
  save: async (guildId) => {
    set({ saving: true, feedback: null });
    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/tickets/config`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(get().config),
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
  saveEditingPanel: async (guildId) => {
    const editing = get().editingPanel;
    if (!editing) return false;

    if (!editing.name.trim()) {
      set({ feedback: "Panel name is required.", feedbackIsError: true });
      return false;
    }

    // A panel is only useful once it has a target channel, and publishing
    // requires one. Enforce it at save time so every stored panel is
    // publishable (no silently un-publishable drafts).
    if (!editing.channel_id) {
      set({
        feedback: "Select a channel before saving this panel.",
        feedbackIsError: true,
      });
      return false;
    }

    const others = get().panels.filter((panel) => panel.id !== editing.id);
    const nextPanels = [...others, { ...editing, name: editing.name.trim() }];

    set({ panelsSaving: true, feedback: null });
    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/tickets/panels`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ panels: nextPanels }),
        }
      );

      if (!response.ok) {
        set({
          feedback: `Save failed: ${await response.text()}`,
          feedbackIsError: true,
        });
        return false;
      }

      const body = (await response.json()) as { panels: TicketPanel[] };
      set({
        panels: body.panels ?? nextPanels,
        editingPanel: null,
        feedback: `Panel saved at ${new Date().toLocaleTimeString()}.`,
        feedbackIsError: false,
      });
      return true;
    } catch {
      set({
        feedback: "Save failed: could not reach the API.",
        feedbackIsError: true,
      });
      return false;
    } finally {
      set({ panelsSaving: false });
    }
  },
  deletePanel: async (guildId, panelId) => {
    const nextPanels = get().panels.filter((panel) => panel.id !== panelId);
    set({ panelsSaving: true, feedback: null });
    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/tickets/panels`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ panels: nextPanels }),
        }
      );

      if (!response.ok) {
        set({
          feedback: `Delete failed: ${await response.text()}`,
          feedbackIsError: true,
        });
        return;
      }

      const body = (await response.json()) as { panels: TicketPanel[] };
      set({
        panels: body.panels ?? nextPanels,
        feedback: "Panel deleted.",
        feedbackIsError: false,
      });
    } catch {
      set({
        feedback: "Delete failed: could not reach the API.",
        feedbackIsError: true,
      });
    } finally {
      set({ panelsSaving: false });
    }
  },
  publishPanelById: async (guildId, panelId) => {
    set({ publishingPanelId: panelId, feedback: null });
    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/tickets/panels/${panelId}/publish`),
        { method: "POST" }
      );

      if (response.ok) {
        await get().loadPanels(guildId);
        set({
          feedback: "Panel published to Discord.",
          feedbackIsError: false,
        });
      } else {
        const body = await response.json().catch(() => null);
        set({
          feedback: `Publish failed: ${body?.detail ?? `HTTP ${response.status}`}`,
          feedbackIsError: true,
        });
      }
    } catch {
      set({
        feedback: "Publish failed: could not reach the API.",
        feedbackIsError: true,
      });
    } finally {
      set({ publishingPanelId: null });
    }
  },
  viewTranscript: async (guildId, ticket) => {
    try {
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/tickets/${ticket.id}/transcript`),
        { cache: "no-store" }
      );

      if (!response.ok) {
        set({
          feedback: "No transcript available for this ticket.",
          feedbackIsError: true,
        });
        return;
      }

      const body = (await response.json()) as { transcript: string };
      set({
        transcript: { ticketNumber: ticket.number, text: body.transcript },
      });
    } catch {
      set({
        feedback: "Could not load the transcript.",
        feedbackIsError: true,
      });
    }
  },
}));
