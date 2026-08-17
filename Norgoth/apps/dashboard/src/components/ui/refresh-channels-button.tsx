"use client";

import { cilReload } from "@coreui/icons";
import { CFormLabel } from "@coreui/react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  useGuildStore,
  type ResourceRefreshKind,
} from "@/stores/guild-store";
import { useLocaleDict } from "@/lib/locale-dict";

function refreshErrorMessage(
  dict: ReturnType<typeof useLocaleDict>,
  code: string | null,
  fallback: string | null,
  kind: ResourceRefreshKind,
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
      return (
        fallback ||
        (kind === "roles"
          ? dict.common.refreshRolesError
          : dict.common.refreshChannelsError)
      );
  }
}

function GuildResourceRefreshButton({ kind }: { kind: ResourceRefreshKind }) {
  const dict = useLocaleDict();
  const refreshResources = useGuildStore((s) => s.refreshResources);
  const refreshing = useGuildStore((s) => s.refreshingChannels);
  const refreshingKind = useGuildStore((s) => s.refreshingKind);
  const loading = useGuildStore((s) => s.loading);
  const notice = useGuildStore((s) => s.channelRefreshNotice);
  const disabled = refreshing || loading;
  const label =
    kind === "roles" ? dict.common.refreshRoles : dict.common.refreshChannels;
  const loadingLabel =
    kind === "roles"
      ? dict.common.refreshingRoles
      : dict.common.refreshingChannels;
  const shown = notice?.kind === kind ? notice : null;
  const showLoading = refreshing && refreshingKind === kind;

  let liveText: string | null = null;
  let liveClass = "small text-body-secondary";
  if (showLoading) {
    liveText = loadingLabel;
  } else if (shown?.type === "success") {
    liveText =
      kind === "roles"
        ? dict.common.refreshRolesSuccess
        : dict.common.refreshChannelsSuccess;
    liveClass = "small text-success";
  } else if (shown?.type === "warning") {
    liveText =
      kind === "roles"
        ? dict.common.refreshRolesCached
        : dict.common.refreshChannelsCached;
    liveClass = "small text-warning";
  } else if (shown?.type === "error") {
    liveText = refreshErrorMessage(dict, shown.code, shown.message, kind);
    liveClass = "small text-danger";
  }

  return (
    <div className="d-flex flex-column align-items-end gap-1">
      <div
        className={liveClass}
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {liveText ?? "\u00a0"}
      </div>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        disabled={disabled}
        aria-busy={refreshing}
        onClick={() => void refreshResources(kind)}
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
    </div>
  );
}

export function RefreshChannelsButton() {
  return <GuildResourceRefreshButton kind="channels" />;
}

export function RefreshRolesButton() {
  return <GuildResourceRefreshButton kind="roles" />;
}

function ResourcePickerToolbar({
  label,
  htmlFor,
  kind,
}: {
  label: string;
  htmlFor?: string;
  kind: ResourceRefreshKind;
}) {
  return (
    <div className="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
      <CFormLabel htmlFor={htmlFor} className="mb-0">
        {label}
      </CFormLabel>
      <GuildResourceRefreshButton kind={kind} />
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
    <ResourcePickerToolbar label={label} htmlFor={htmlFor} kind="channels" />
  );
}

export function RolePickerToolbar({
  label,
  htmlFor,
}: {
  label: string;
  htmlFor?: string;
}) {
  return <ResourcePickerToolbar label={label} htmlFor={htmlFor} kind="roles" />;
}
