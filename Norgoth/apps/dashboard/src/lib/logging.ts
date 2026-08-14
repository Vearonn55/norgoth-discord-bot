/**
 * Pure, dependency-free helpers for the logging configuration UI. Kept separate
 * from the Zustand store and React components so they are trivially unit-testable.
 */

/** Convert a Discord decimal colour to a #RRGGBB hex string. */
export function colorToHex(value: number | null | undefined): string {
  if (value == null) return "#5865f2";
  return `#${(value & 0xffffff).toString(16).padStart(6, "0")}`;
}

/** Parse a #RRGGBB (or RRGGBB) hex string into a Discord decimal, or null. */
export function hexToColor(hex: string): number | null {
  const cleaned = hex.replace("#", "").trim();
  if (!/^[0-9a-fA-F]{6}$/.test(cleaned)) return null;
  return parseInt(cleaned, 16);
}

/**
 * Sanitize a user-provided channel name to Discord's constraints: lowercase,
 * spaces to hyphens, invalid characters stripped, and capped at 90 chars.
 * Always returns a non-empty string ("log" as a fallback).
 */
export function sanitizeChannelName(value: string): string {
  return (
    value
      .toLowerCase()
      .replace(/[^a-z0-9\- ]/g, "")
      .trim()
      .replace(/\s+/g, "-")
      .slice(0, 90) || "log"
  );
}

/**
 * Split a stored channel name into an optional leading emoji token and the
 * remaining sanitizable name. Understands custom (`<:name:id>`) and shortcode
 * (`:name:`) emoji, plus a leading unicode emoji sequence (multi-codepoint /
 * ZWJ / skin-tone safe via code-point iteration — no UTF-16 slicing).
 *
 * Accepts both the legacy `emoji-name` form (Discord turned a space into `-`)
 * and the canonical `emojiname` form with no separator.
 */
export function splitEmojiName(full: string): { emoji: string; name: string } {
  const trimmed = (full ?? "").trim();
  const token = trimmed.match(/^(<a?:\w+:\d+>|:[\w~+-]+:)[\s\-]*(.*)$/);
  if (token) return { emoji: token[1], name: token[2].trim() };

  const chars = [...trimmed];
  if (chars.length === 0) return { emoji: "", name: "" };

  // Consume consecutive non-ASCII / non-alphanumeric code points as the emoji
  // token. Stops at the first a-z / 0-9 / hyphen so multi-codepoint sequences
  // (ZWJ families, skin tones, variation selectors) stay intact.
  if (!/[a-z0-9\- ]/i.test(chars[0])) {
    let end = 0;
    while (end < chars.length && !/[a-z0-9]/i.test(chars[end])) {
      // Skip a trailing separator hyphen that Discord may have inserted
      // between emoji and text (legacy `🔥-chat-logs` form).
      if (chars[end] === "-" && end > 0) {
        end += 1;
        break;
      }
      if (chars[end] === " " || chars[end] === "-") {
        end += 1;
        break;
      }
      end += 1;
    }
    const emoji = chars.slice(0, end).join("").replace(/[\s\-]+$/, "");
    const name = chars.slice(end).join("").replace(/^[\s\-]+/, "");
    return { emoji, name };
  }
  return { emoji: "", name: trimmed };
}

/**
 * Compose a Discord text-channel name from an optional emoji and a raw name.
 *
 * Rule: emoji + sanitizedText with NO separator.
 * Example: emoji "🔥" + "Chat Logs" → "🔥chat-logs"
 */
export function composeChannelName(emoji: string, name: string): string {
  const base = sanitizeChannelName(name);
  return emoji ? `${emoji}${base}` : base;
}

/**
 * Compose a Discord category name from an optional emoji and a raw name.
 * Categories allow spaces, so the emoji is joined with a single space.
 */
export function composeCategoryName(emoji: string, name: string): string {
  const base = name.trim() || "NorBot Logs";
  return emoji ? `${emoji} ${base}` : base;
}
