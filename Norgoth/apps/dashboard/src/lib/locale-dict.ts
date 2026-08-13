"use client";

import { useParams } from "next/navigation";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";

export type LocaleDict = typeof en;

/** Server-safe locale dictionary picker. */
export function getLocaleDict(lang: string): LocaleDict {
  return lang === "tr" ? tr : en;
}

/**
 * Client-safe full dictionary for the active `[lang]` route param.
 * Prefer section-specific hooks for large surfaces when already established
 * (e.g. useContentNotificationsCopy); use this for shared chrome and panels.
 */
export function useLocaleDict(): LocaleDict {
  const params = useParams();
  const lang = String(params?.lang || "en");
  return getLocaleDict(lang);
}

/** Replace `{name}` style tokens in a dictionary template string. */
export function formatDict(
  template: string,
  values: Record<string, string | number>,
): string {
  return Object.entries(values).reduce(
    (text, [key, value]) => text.replaceAll(`{${key}}`, String(value)),
    template,
  );
}
