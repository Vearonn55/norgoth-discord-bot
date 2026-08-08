import "server-only";
import { locales, type Locale } from "@/i18n/config";

const dictionaries = {
  en: () => import("@/dictionaries/en.json").then((m) => m.default),
  tr: () => import("@/dictionaries/tr.json").then((m) => m.default),
};

export type Dictionary = Awaited<ReturnType<(typeof dictionaries)["en"]>>;

export function hasLocale(locale: string): locale is Locale {
  return locales.includes(locale as Locale);
}

export async function getDictionary(locale: Locale) {
  return dictionaries[locale]();
}
