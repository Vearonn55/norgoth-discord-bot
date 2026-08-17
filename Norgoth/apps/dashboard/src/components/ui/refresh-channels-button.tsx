"use client";

import { cilReload } from "@coreui/icons";
import { CFormLabel } from "@coreui/react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { useGuildStore } from "@/stores/guild-store";
import { useLocaleDict } from "@/lib/locale-dict";

function refreshErrorMessage(
  dict: ReturnType<typeof useLocaleDict>,
  code: string | null,
  fallback: string | null,
): string {
  switch (code) {
    case "discord_rate_limited":
      return dict.common.discordRateLimited;
    case "bot_not_installed":
      return dict.common.botNotInstalled;
    case "missing_bot_permissions":
      return dict.common.missingBotPermissions;
    case "discord_temporarily_unavailable":
      return dict.common.discordTemporarilyUnavailable;
    default:
      return fallback || dict.common.refreshChannelsError;
  }
}

export function RefreshChannelsButton() {
  const dict = useLocaleDict();
  const refreshChannels = useGuildStore((s) => s.refreshChannels);
  const refreshing = useGuildStore((s) => s.refreshingChannels);
  const loading = useGuildStore((s) => s.loading);
  const notice = useGuildStore((s) => s.channelRefreshNotice);
  const disabled = refreshing || loading;
  const label = dict.common.refreshChannels;

  return (
    <div className="d-flex flex-column align-items-end gap-1">
      <Button
        type="button"
        variant="secondary"
        size="sm"
        disabled={disabled}
        onClick={() => void refreshChannels()}
        aria-label={label}
        title={label}
        className="d-inline-flex align-items-center gap-2"
      >
        <Icon
          icon={cilReload}
          size="sm"
          className={refreshing ? "norgoth-refresh-spin" : undefined}
        />
        <span>{label}</span>
      </Button>
      {notice?.type === "success" ? (
        <span className="small text-success">{dict.common.refreshChannelsSuccess}</span>
      ) : null}
      {notice?.type === "error" ? (
        <span className="small text-danger">
          {refreshErrorMessage(dict, notice.code, notice.message)}
        </span>
      ) : null}
    </div>
  );
}

export function ChannelPickerToolbar({
  label,
  htmlFor,
}: {
  label: string;
  htmlFor?: string;
}) {
  return (
    <div className="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
      <CFormLabel htmlFor={htmlFor} className="mb-0">
        {label}
      </CFormLabel>
      <RefreshChannelsButton />
    </div>
  );
}
