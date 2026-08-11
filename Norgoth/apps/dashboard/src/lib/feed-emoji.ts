"use client";

import { parseStoredEmoji } from "@/lib/discord/emoji-data";
import type { FeedEmoji } from "@/stores/feed-channels-store";

/** Convert DiscordEmojiPicker wire value → FeedEmoji API shape. */
export function feedEmojiFromPicker(value: string): FeedEmoji | null {
  const parsed = parseStoredEmoji(value);
  if (parsed.kind === "empty") return null;
  if (parsed.kind === "custom" && parsed.id && parsed.name) {
    const reaction = parsed.animated
      ? `a:${parsed.name}:${parsed.id}`
      : `${parsed.name}:${parsed.id}`;
    return {
      kind: "custom",
      id: parsed.id,
      name: parsed.name,
      animated: Boolean(parsed.animated),
      reaction,
    };
  }
  const char = parsed.char || value.trim();
  if (!char) return null;
  return {
    kind: "unicode",
    id: null,
    name: char,
    animated: false,
    reaction: char,
  };
}

/** Convert FeedEmoji → picker string value. */
export function feedEmojiToPicker(emoji: FeedEmoji | null | undefined): string {
  if (!emoji) return "";
  if (emoji.kind === "custom" && emoji.id) {
    return emoji.animated
      ? `a:${emoji.name}:${emoji.id}`
      : `${emoji.name}:${emoji.id}`;
  }
  return emoji.reaction || emoji.name || "";
}
