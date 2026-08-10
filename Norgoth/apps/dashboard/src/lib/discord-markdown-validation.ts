/** True when Discord markdown is empty after TinyMCE scaffolding trim. */
export function isBlankDiscordMarkdown(markdown: string | null | undefined): boolean {
  return !String(markdown ?? "").trim();
}

/** Validate markdown length for Discord-bound fields (after normalization). */
export function assertDiscordMarkdownLength(
  markdown: string,
  maxLength: number
): { ok: boolean; reason?: "empty" | "too_long"; trimmed: string } {
  const trimmed = markdown.trim();
  if (!trimmed) {
    return { ok: false, reason: "empty", trimmed };
  }
  if (trimmed.length > maxLength) {
    return { ok: false, reason: "too_long", trimmed };
  }
  return { ok: true, trimmed };
}
