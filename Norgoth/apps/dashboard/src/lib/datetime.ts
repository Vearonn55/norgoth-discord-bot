/**
 * Shared, locale-aware date/time formatting for admin-facing timestamps.
 *
 * The backend always emits UTC ISO-8601 strings (e.g. `now_iso()`); this module
 * is the single presentation-layer formatter. It parses the ISO instant and
 * renders it in the browser's local timezone (so the displayed instant is
 * correct) using the app's active locale. Do NOT introduce per-feature
 * formatters — reuse these helpers everywhere admin timestamps are shown.
 */

export type SupportedLocale = "en" | "tr";

/** Maps the app locale to a BCP-47 tag understood by `Intl`. */
export function toIntlLocale(locale: string | null | undefined): string {
  return locale === "tr" ? "tr-TR" : "en-US";
}

/** Placeholder used when a value is missing or cannot be parsed. */
export const EMPTY_DATE_PLACEHOLDER = "—";

function parseInstant(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * Format an ISO timestamp as localized date + HH:mm:ss (24h).
 * Example (en): "Aug 10, 2026 - 14:02:35"; (tr): "10 Ağu 2026 - 14:02:35".
 */
export function formatDateTime(
  iso: string | null | undefined,
  locale: string | null | undefined
): string {
  const date = parseInstant(iso);
  if (!date) return EMPTY_DATE_PLACEHOLDER;

  const intlLocale = toIntlLocale(locale);
  const datePart = new Intl.DateTimeFormat(intlLocale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
  const timePart = new Intl.DateTimeFormat(intlLocale, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).format(date);
  return `${datePart} - ${timePart}`;
}

/**
 * Compact date + time with seconds, suited to dense selectors/tables.
 */
export function formatDateTimeShort(
  iso: string | null | undefined,
  locale: string | null | undefined
): string {
  const date = parseInstant(iso);
  if (!date) return EMPTY_DATE_PLACEHOLDER;

  return new Intl.DateTimeFormat(toIntlLocale(locale), {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).format(date);
}
