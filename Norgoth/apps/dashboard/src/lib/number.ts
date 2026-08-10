/**
 * Shared, locale-aware number formatting for admin-facing counts.
 *
 * Reuses the same locale mapping as the datetime formatter so grouping
 * separators follow the active app locale (e.g. en: "12,345"; tr: "12.345").
 */

import { toIntlLocale } from "@/lib/datetime";

/** Placeholder used when a numeric value is missing. */
export const EMPTY_NUMBER_PLACEHOLDER = "—";

/**
 * Format an integer/float with locale-aware grouping separators.
 * Returns a dash placeholder for null/undefined/NaN values.
 */
export function formatNumber(
  value: number | null | undefined,
  locale: string | null | undefined
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return EMPTY_NUMBER_PLACEHOLDER;
  }
  return new Intl.NumberFormat(toIntlLocale(locale)).format(value);
}
