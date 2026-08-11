import type {
  LoggingCatalog,
  LoggingChannelConfig,
  LoggingConfig,
  LoggingGroupDef,
} from "@/stores/logging-config-store";

export type LoggingCategoryCard = LoggingChannelConfig & {
  /** True when a guild-specific logging_channels row exists. */
  configured: boolean;
  /** Catalog label for display (falls back to key). */
  label: string;
};

function slugNameFromLabel(label: string, key: string): string {
  const slug = label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `${slug || key}-logs`;
}

/**
 * Merge the supported category catalog with guild channel rows so every
 * category is visible — including ones never selected during setup.
 */
export function mergeLoggingCategories(
  catalog: LoggingCatalog | null | undefined,
  config: LoggingConfig | null | undefined
): LoggingCategoryCard[] {
  const groups: LoggingGroupDef[] = catalog?.groups ?? [];
  const byKey = new Map(
    (config?.channels ?? []).map((channel) => [channel.key, channel])
  );

  // Prefer catalog order; append any orphan guild rows not in the catalog.
  const cards: LoggingCategoryCard[] = [];
  const seen = new Set<string>();

  for (const group of groups) {
    seen.add(group.key);
    const existing = byKey.get(group.key);
    if (existing) {
      cards.push({
        ...existing,
        configured: true,
        label: group.label,
      });
      continue;
    }
    cards.push({
      key: group.key,
      name: slugNameFromLabel(group.label, group.key),
      channel_id: null,
      norgoth_managed: true,
      default_color: group.default_color,
      position: cards.length,
      enabled: false,
      configured: false,
      label: group.label,
    });
  }

  for (const channel of config?.channels ?? []) {
    if (seen.has(channel.key)) continue;
    cards.push({
      ...channel,
      configured: true,
      label: channel.name || channel.key,
    });
  }

  return cards;
}
