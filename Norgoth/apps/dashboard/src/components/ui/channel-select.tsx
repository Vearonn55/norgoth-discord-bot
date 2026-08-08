"use client";

import { CFormSelect } from "@coreui/react";
import type { GuildChannel } from "@/stores/guild-store";

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
  return (
    <CFormSelect
      id={id}
      className={className}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {allowEmpty ? <option value="">{emptyLabel}</option> : null}
      {channels.map((channel) => (
        <option key={channel.id} value={channel.id}>
          #{channel.name}
          {channel.category ? ` (${channel.category})` : ""}
        </option>
      ))}
    </CFormSelect>
  );
}
