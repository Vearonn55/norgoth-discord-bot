/** Client-side gate matching Auto Response save rules (markdown after TinyMCE). */
export function isValidAutoResponseMarkdown(markdown: string): {
  ok: boolean;
  reason?: "empty" | "too_long";
} {
  const trimmed = markdown.trim();
  if (!trimmed) {
    return { ok: false, reason: "empty" };
  }
  if (trimmed.length > 1500) {
    return { ok: false, reason: "too_long" };
  }
  return { ok: true };
}
