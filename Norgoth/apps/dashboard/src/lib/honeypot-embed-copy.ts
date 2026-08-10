import type { EmbedMessage } from "@/stores/embed-messages-store";

/** Copy Embed Library draft into honeypot snapshot (no live reference). */
export function copyEmbedIntoHoneypot(message: EmbedMessage): {
  warning_content: string;
  warning_embed: Record<string, unknown> | null;
} {
  return {
    warning_content: message.content ?? "",
    warning_embed: message.embed_json
      ? ({ ...message.embed_json } as Record<string, unknown>)
      : null,
  };
}
