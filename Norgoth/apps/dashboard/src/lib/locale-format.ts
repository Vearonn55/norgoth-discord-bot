import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";

export type LocaleDict = typeof en;

/** Locale dictionary picker — safe on server and client. */
export function getLocaleDict(lang: string): LocaleDict {
  return lang === "tr" ? tr : en;
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
