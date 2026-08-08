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
 * (`:name:`) emoji, plus a single leading unicode emoji glyph.
 */
export function splitEmojiName(full: string): { emoji: string; name: string } {
  const trimmed = (full ?? "").trim();
  const token = trimmed.match(/^(<a?:\w+:\d+>|:[\w~+-]+:)\s*(.*)$/);
  if (token) return { emoji: token[1], name: token[2].trim() };

  const first = [...trimmed][0];
  if (first && !/[a-z0-9\- ]/i.test(first)) {
    return { emoji: first, name: trimmed.slice(first.length).trim() };
  }
  return { emoji: "", name: trimmed };
}

/** Compose a Discord channel name from an optional emoji and a raw name. */
export function composeChannelName(emoji: string, name: string): string {
  const base = sanitizeChannelName(name);
  return emoji ? `${emoji} ${base}` : base;
}
