/**
 * Maps @emoji-mart/data into Norgoth picker categories.
 */

import type { EmojiMartData } from "@emoji-mart/data";
import type { EmojiCategory, UnicodeEmojiItem } from "@/lib/discord/emoji-data";

const CATEGORY_LABELS: Record<string, string> = {
  people: "Smileys & People",
  nature: "Animals & Nature",
  foods: "Food & Drink",
  activity: "Activities",
  places: "Travel & Places",
  objects: "Objects",
  symbols: "Symbols",
  flags: "Flags",
};

const CATEGORY_ORDER = [
  "people",
  "nature",
  "foods",
  "activity",
  "places",
  "objects",
  "symbols",
  "flags",
] as const;

function humanizeId(id: string): string {
  return id.replace(/[_-]+/g, " ").trim();
}

export function mapEmojiMartData(data: EmojiMartData): EmojiCategory[] {
  const byId = new Map<string, UnicodeEmojiItem>();

  for (const emoji of Object.values(data.emojis)) {
    const skins = emoji.skins?.map((s) => s.native).filter(Boolean) ?? [];
    if (skins.length === 0) continue;

    const name = (emoji.name || humanizeId(emoji.id)).toLowerCase();
    const keywords = [
      name,
      emoji.id,
      humanizeId(emoji.id),
      ...(emoji.keywords ?? []),
      ...(emoji.emoticons ?? []),
    ]
      .map((k) => k.toLowerCase())
      .filter(Boolean);

    byId.set(emoji.id, {
      id: emoji.id,
      char: skins[0],
      name,
      keywords: Array.from(new Set(keywords)),
      skins: skins.length > 1 ? skins : undefined,
    });
  }

  // Resolve aliases so search/category ids stay stable.
  for (const [alias, target] of Object.entries(data.aliases ?? {})) {
    const item = byId.get(target);
    if (!item) continue;
    const extra = [alias, humanizeId(alias)].map((k) => k.toLowerCase());
    item.keywords = Array.from(new Set([...item.keywords, ...extra]));
  }

  const categories: EmojiCategory[] = [];
  for (const id of CATEGORY_ORDER) {
    const source = data.categories.find((c) => c.id === id);
    if (!source) continue;
    const emojis = source.emojis
      .map((emojiId) => byId.get(emojiId))
      .filter((e): e is UnicodeEmojiItem => Boolean(e));
    if (emojis.length === 0) continue;
    categories.push({
      id,
      label: CATEGORY_LABELS[id] ?? id,
      emojis,
    });
  }

  return categories;
}
