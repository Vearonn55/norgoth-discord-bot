"use client";

import { useParams } from "next/navigation";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";

export type FeatureInfoContent = {
  title: string;
  description: string;
  usage?: string;
  alertActive?: string;
  alertInactive?: string;
};

/** Keys available under the `featureInfo` dictionary namespace. */
export type FeatureInfoKey = keyof typeof en.featureInfo;

type FeatureInfoMap = Record<string, FeatureInfoContent>;

/**
 * Client-safe feature-info resolver. Statically imports both locale
 * dictionaries and selects content by the active `lang` route param so both
 * server pages and client panels can source localized header help without the
 * server-only `getDictionary` loader.
 */
export function useFeatureInfo(
  key: FeatureInfoKey | string | undefined
): FeatureInfoContent | null {
  const params = useParams();
  const lang = String(params?.lang || "en");
  if (!key) return null;

  const dict = (lang === "tr" ? tr.featureInfo : en.featureInfo) as FeatureInfoMap;
  return dict[key] ?? null;
}
