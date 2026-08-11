/**
 * Unicode emoji catalog for the Discord-like picker.
 * Standard emoji come from @emoji-mart/data (lazy-loaded).
 * Custom guild emojis come from guild resources separately.
 */

export type UnicodeEmojiItem = {
  id: string;
  char: string;
  name: string;
  keywords: string[];
  /** Native Unicode variants when skin tones exist (index 0 = default). */
  skins?: string[];
};

export type EmojiCategory = {
  id: string;
  label: string;
  emojis: UnicodeEmojiItem[];
};

const RECENT_KEY = "norgoth:emoji-recent:v1";
const RECENT_MAX = 24;

let cachedCategories: EmojiCategory[] | null = null;
let loadPromise: Promise<EmojiCategory[]> | null = null;

/** Category stubs for tab labels before full catalog loads. */
export const UNICODE_EMOJI_CATEGORY_META: Array<{ id: string; label: string }> =
  [
    { id: "people", label: "Smileys & People" },
    { id: "nature", label: "Animals & Nature" },
    { id: "foods", label: "Food & Drink" },
    { id: "activity", label: "Activities" },
    { id: "places", label: "Travel & Places" },
    { id: "objects", label: "Objects" },
    { id: "symbols", label: "Symbols" },
    { id: "flags", label: "Flags" },
  ];

export function getUnicodeEmojiCategoriesSync(): EmojiCategory[] {
  return cachedCategories ?? [];
}

export async function loadUnicodeEmojiCategories(): Promise<EmojiCategory[]> {
  if (cachedCategories) return cachedCategories;
  if (!loadPromise) {
    loadPromise = (async () => {
      const mod = await import("@emoji-mart/data");
      const data = ("default" in mod && mod.default ? mod.default : mod) as import("@emoji-mart/data").EmojiMartData;
      const { mapEmojiMartData } = await import(
        "@/lib/discord/emoji-mart-adapter"
      );
      cachedCategories = mapEmojiMartData(data);
      return cachedCategories;
    })().catch((err) => {
      loadPromise = null;
      throw err;
    });
  }
  return loadPromise;
}

export type GuildEmojiItem = {
  id: string;
  name: string;
  animated?: boolean;
};

/** Wire format for custom emoji stored on role menu entries. */
export function encodeGuildEmoji(emoji: GuildEmojiItem): string {
  const prefix = emoji.animated ? "a:" : "";
  return `${prefix}${emoji.name}:${emoji.id}`;
}

export function parseStoredEmoji(value: string | null | undefined): {
  kind: "unicode" | "custom" | "empty";
  char?: string;
  name?: string;
  id?: string;
  animated?: boolean;
} {
  if (!value || !value.trim()) return { kind: "empty" };
  const raw = value.trim();

  // Discord mention form <:name:id> or <a:name:id>
  const mention = raw.match(/^<(a?):([a-zA-Z0-9_]+):(\d+)>$/);
  if (mention) {
    return {
      kind: "custom",
      animated: mention[1] === "a",
      name: mention[2],
      id: mention[3],
    };
  }

  // Stored wire: name:id or a:name:id
  const custom = raw.match(/^(a:)?([a-zA-Z0-9_]+):(\d+)$/);
  if (custom) {
    return {
      kind: "custom",
      animated: Boolean(custom[1]),
      name: custom[2],
      id: custom[3],
    };
  }

  return { kind: "unicode", char: raw };
}

export function emojiPreviewSrc(value: string | null | undefined): {
  type: "unicode" | "image" | "none";
  text?: string;
  url?: string;
} {
  const parsed = parseStoredEmoji(value);
  if (parsed.kind === "empty") return { type: "none" };
  if (parsed.kind === "unicode") {
    return { type: "unicode", text: parsed.char };
  }
  const ext = parsed.animated ? "gif" : "png";
  return {
    type: "image",
    url: `https://cdn.discordapp.com/emojis/${parsed.id}.${ext}?size=48`,
    text: parsed.name,
  };
}

export function getRecentEmojis(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(RECENT_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed)
      ? parsed.filter((x): x is string => typeof x === "string").slice(0, RECENT_MAX)
      : [];
  } catch {
    return [];
  }
}

export function pushRecentEmoji(value: string): void {
  if (typeof window === "undefined" || !value.trim()) return;
  const next = [
    value,
    ...getRecentEmojis().filter((item) => item !== value),
  ].slice(0, RECENT_MAX);
  try {
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    // ignore quota
  }
}

export function resolveEmojiChar(
  emoji: UnicodeEmojiItem,
  skinToneIndex = 0
): string {
  if (emoji.skins && emoji.skins.length > 0) {
    return emoji.skins[Math.min(skinToneIndex, emoji.skins.length - 1)] ?? emoji.char;
  }
  return emoji.char;
}

export function filterUnicodeEmojis(
  query: string,
  categories: EmojiCategory[]
): UnicodeEmojiItem[] {
  const q = query.trim().toLowerCase();
  const all = categories.flatMap((c) => c.emojis);
  if (!q) return all;
  return all.filter(
    (e) =>
      e.name.includes(q) ||
      e.char.includes(q) ||
      e.id.toLowerCase().includes(q) ||
      e.keywords.some((k) => k.includes(q))
  );
}

/** Skin-tone preview glyphs for the picker tone bar (index 0 = default). */
export const SKIN_TONE_SWATCHES = ["✋", "✋🏻", "✋🏼", "✋🏽", "✋🏾", "✋🏿"] as const;
