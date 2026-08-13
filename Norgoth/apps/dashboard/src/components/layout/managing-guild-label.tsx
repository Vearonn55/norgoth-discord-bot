"use client";

import { formatDict, useLocaleDict } from "@/lib/locale-dict";
import { useGuildStore } from "@/stores/guild-store";

type ManagingGuildLabelProps = {
  /** Shown while the selected guild is still hydrating. */
  loadingFallback?: string;
  /** Shown when no guild is selected. */
  emptyFallback?: string;
};

/**
 * Localized “Managing {guild}” line driven by the selected-guild store.
 * Never falls back to bot/health guilds[0] or a hard-coded server name.
 */
export function ManagingGuildLabel({
  loadingFallback,
  emptyFallback,
}: ManagingGuildLabelProps) {
  const dict = useLocaleDict();
  const selectedGuild = useGuildStore((s) => s.selectedGuild);
  const guildId = useGuildStore((s) => s.guildId);
  const loading = useGuildStore((s) => s.loading);

  if (selectedGuild?.name) {
    return (
      <>
        {formatDict(dict.dashboard.managingGuild, {
          name: selectedGuild.name,
        })}
      </>
    );
  }

  if (loading || (guildId && !selectedGuild)) {
    return <>{loadingFallback ?? dict.common.loading}</>;
  }

  return (
    <>
      {emptyFallback ??
        dict.sidebar.noServerSelected ??
        dict.dashboard.descriptionFallback}
    </>
  );
}
