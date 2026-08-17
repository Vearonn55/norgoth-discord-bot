"use client";

import { CFormSelect } from "@coreui/react";
import type { GuildChannel } from "@/stores/guild-store";
import { useLocaleDict } from "@/lib/locale-dict";

type ChannelSelectProps = {
  channels: GuildChannel[];
  value: string;
  onChange: (value: string) => void;
  allowEmpty?: boolean;
  emptyLabel?: string;
  id?: string;
  className?: string;
};

export function ChannelSelect({
  channels,
  value,
  onChange,
  allowEmpty = true,
  emptyLabel = "Select channel…",
  id,
  className,
}: ChannelSelectProps) {
  const dict = useLocaleDict();
  const selectedMissing =
    Boolean(value) && !channels.some((channel) => channel.id === value);

  return (
    <CFormSelect
      id={id}
      className={className}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {allowEmpty ? <option value="">{emptyLabel}</option> : null}
      {selectedMissing ? (
        <option value={value} disabled>
          {dict.common.channelUnavailable}
        </option>
      ) : null}
      {channels.map((channel) => (
        <option key={channel.id} value={channel.id}>
          #{channel.name}
          {channel.category ? ` (${channel.category})` : ""}
        </option>
      ))}
    </CFormSelect>
  );
}
