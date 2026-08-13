"use client";

import { useParams } from "next/navigation";
import {
  formatDict,
  getLocaleDict,
  type LocaleDict,
} from "@/lib/locale-format";

export type { LocaleDict };
export { formatDict, getLocaleDict };

/**
 * Full dictionary for the active `[lang]` route param.
 * Client Components only.
 */
export function useLocaleDict(): LocaleDict {
  const params = useParams();
  const lang = String(params?.lang || "en");
  return getLocaleDict(lang);
}
